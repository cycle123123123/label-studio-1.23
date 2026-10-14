"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import csv
import logging
import os
import pathlib
from datetime import timedelta

from core.feature_flags import flag_set
from core.filters import ListFilter
from core.label_config import config_essential_data_has_changed
from core.mixins import GetParentObjectMixin
from core.permissions import ViewClassPermission, all_permissions
from core.redis import start_job_async_or_sync
from core.utils.common import paginator, paginator_help, temporary_disconnect_all_signals
from core.utils.exceptions import LabelStudioDatabaseException, ProjectExistException
from core.utils.filterset_to_openapi_params import filterset_to_openapi_params
from core.utils.io import find_dir, find_file, read_yaml
from core.utils.serializer_to_openapi_params import serializer_to_openapi_params
from data_manager.functions import filters_ordering_selected_items_exist, get_prepared_queryset
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django_filters import CharFilter, FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from label_studio_sdk.label_interface.interface import LabelInterface
from ml.serializers import MLBackendSerializer
from projects.functions.next_task import get_next_task
from projects.functions.stream_history import get_label_stream_history
from projects.functions.utils import recalculate_created_annotations_and_labels_from_scratch
from projects.models import Project, ProjectImport, ProjectManager, ProjectReimport, ProjectSummary
from projects.serializers import (
    GetFieldsSerializer,
    ProjectCountsSerializer,
    ProjectImportSerializer,
    ProjectLabelConfigSerializer,
    ProjectModelVersionExtendedSerializer,
    ProjectModelVersionParamsSerializer,
    ProjectReimportSerializer,
    ProjectSerializer,
    ProjectSummarySerializer,
)
from rest_framework import filters, generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as RestValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler
from tasks.assignment import (
    apply_task_assignments,
    can_manage_assignments,
    get_assignable_users,
    is_assignment_enforced_for_user,
)
from tasks.models import Annotation, Task, TaskAssignment, TaskAssignmentAuditLog, TaskWorkflowAuditLog
from tasks.serializers import (
    NextTaskSerializer,
    TaskSerializer,
    TaskSimpleSerializer,
    TaskWithAnnotationsAndPredictionsAndDraftsSerializer,
)
from users.models import User
from users.serializers import UserSimpleSerializer
from webhooks.models import WebhookAction
from webhooks.utils import api_webhook, api_webhook_for_delete, emit_webhooks_for_instance

from label_studio.core.utils.common import load_func

logger = logging.getLogger(__name__)

ProjectImportPermission = load_func(settings.PROJECT_IMPORT_PERMISSION)

_result_schema = {
    'title': 'Labeling result',
    'description': 'Labeling result (choices, labels, bounding boxes, etc.)',
    'type': 'object',
    'properties': {
        'from_name': {
            'type': 'string',
            'description': 'The name of the labeling tag from the project config',
        },
        'to_name': {
            'type': 'string',
            'description': 'The name of the labeling tag from the project config',
        },
        'value': {
            'type': 'object',
            'description': 'Labeling result value. Format depends on chosen ML backend',
        },
    },
    'example': {'from_name': 'image_class', 'to_name': 'image', 'value': {'labels': ['Cat']}},
}

_task_data_schema = {
    'title': 'Task data',
    'description': 'Task data',
    'type': 'object',
    'example': {'id': 1, 'my_image_url': '/static/samples/kittens.jpg'},
}


class ProjectListPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProjectFilterSet(FilterSet):
    ids = ListFilter(field_name='id', lookup_expr='in')
    title = CharFilter(field_name='title', lookup_expr='icontains')


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='List your projects',
        description="""
    Return a list of the projects that you've created.

    To perform most tasks with the Label Studio API, you must specify the project ID, sometimes referred to as the `pk`.
    To retrieve a list of your Label Studio projects, update the following command to match your own environment.
    Replace the domain name, port, and authorization token, then run the following from the command line:
    ```bash
    curl -X GET {}/api/projects/ -H 'Authorization: Token abc123'
    ```
    """.format(
            settings.HOSTNAME or 'https://localhost:8080'
        ),
        parameters=[
            *serializer_to_openapi_params(GetFieldsSerializer),
            *filterset_to_openapi_params(ProjectFilterSet),
        ],
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'counts',
            'x-fern-audiences': ['public'],
            'x-fern-pagination': {
                'offset': '$request.page',
                'results': '$response.results',
            },
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Create new project',
        description="""
    Create a project and set up the labeling interface in Label Studio using the API.

    ```bash
    curl -H Content-Type:application/json -H 'Authorization: Token abc123' -X POST '{}/api/projects' \
    --data '{{"title": "My project", "label_config": "<View></View>"}}'
    ```
    """.format(
            settings.HOSTNAME or 'https://localhost:8080'
        ),
        request=ProjectSerializer,
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class ProjectListAPI(generics.ListCreateAPIView):
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ProjectSerializer
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = ProjectFilterSet
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        POST=all_permissions.projects_create,
    )
    pagination_class = ProjectListPagination

    def get_queryset(self):
        serializer = GetFieldsSerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data.get('include')
        filter = serializer.validated_data.get('filter')
        projects = Project.objects.filter(organization=self.request.user.active_organization).order_by(
            F('pinned_at').desc(nulls_last=True), '-created_at'
        )
        if filter in ['pinned_only', 'exclude_pinned']:
            projects = projects.filter(pinned_at__isnull=filter == 'exclude_pinned')
        projects = ProjectManager.with_counts_annotate(projects, fields=fields)

        # Only annotate FSM state for UI/API consumption when both feature flags are enabled
        if flag_set('fflag_feat_fit_568_finite_state_management', user=self.request.user) and flag_set(
            'fflag_feat_fit_710_fsm_state_fields', user=self.request.user
        ):
            projects = projects.with_state()

        return projects.prefetch_related('members', 'created_by')

    def get_serializer_context(self):
        context = super(ProjectListAPI, self).get_serializer_context()
        context['created_by'] = self.request.user
        return context

    def perform_create(self, ser):
        try:
            ser.save(organization=self.request.user.active_organization)
        except IntegrityError as e:
            if str(e) == 'UNIQUE constraint failed: project.title, project.created_by_id':
                raise ProjectExistException(
                    'Project with the same name already exists: {}'.format(ser.validated_data.get('title', ''))
                )
            raise LabelStudioDatabaseException('Database error during project creation. Try again.')

    def get(self, request, *args, **kwargs):
        return super(ProjectListAPI, self).get(request, *args, **kwargs)

    @api_webhook(WebhookAction.PROJECT_CREATED)
    def post(self, request, *args, **kwargs):
        return super(ProjectListAPI, self).post(request, *args, **kwargs)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary="List projects' counts",
        parameters=[
            *serializer_to_openapi_params(GetFieldsSerializer),
            *filterset_to_openapi_params(ProjectFilterSet),
        ],
        description='Returns a list of projects with their counts. For example, task_number which is the total task number in project',
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'list_counts',
            'x-fern-audiences': ['public'],
        },
    ),
)
class ProjectCountsListAPI(generics.ListAPIView):
    serializer_class = ProjectCountsSerializer
    filterset_class = ProjectFilterSet
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
    )
    pagination_class = ProjectListPagination

    def get_queryset(self):
        serializer = GetFieldsSerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data.get('include')
        projects = Project.objects.with_counts(fields=fields).filter(
            organization=self.request.user.active_organization
        )

        # Only annotate FSM state for UI/API consumption when both feature flags are enabled
        if flag_set('fflag_feat_fit_568_finite_state_management', user=self.request.user) and flag_set(
            'fflag_feat_fit_710_fsm_state_fields', user=self.request.user
        ):
            projects = projects.with_state()

        return projects


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Get project by ID',
        description='Retrieve information about a project by project ID.',
        responses={
            '200': OpenApiResponse(
                description='Project information',
                response=ProjectSerializer,
                examples=[
                    OpenApiExample(
                        name='response',
                        value={
                            'id': 1,
                            'title': 'My project',
                            'description': 'My first project',
                            'label_config': '<View>[...]</View>',
                            'expert_instruction': 'Label all cats',
                            'show_instruction': True,
                            'show_skip_button': True,
                            'enable_empty_annotation': True,
                            'show_annotation_history': True,
                            'organization': 1,
                            'color': '#FF0000',
                            'maximum_annotations': 1,
                            'is_published': True,
                            'model_version': '1.0.0',
                            'is_draft': False,
                            'created_by': {
                                'id': 1,
                                'first_name': 'Jo',
                                'last_name': 'Doe',
                                'email': 'manager@humansignal.com',
                            },
                            'created_at': '2023-08-24T14:15:22Z',
                            'min_annotations_to_start_training': 0,
                            'start_training_on_annotation_update': True,
                            'show_collab_predictions': True,
                            'num_tasks_with_annotations': 10,
                            'task_number': 100,
                            'useful_annotation_number': 10,
                            'ground_truth_number': 5,
                            'skipped_annotations_number': 0,
                            'total_annotations_number': 10,
                            'total_predictions_number': 0,
                            'sampling': 'Sequential sampling',
                            'annotator_evaluation_enabled': False,
                            'show_overlap_first': True,
                            'overlap_cohort_percentage': 100,
                            'task_data_login': 'user',
                            'task_data_password': 'secret',
                            'control_weights': {},
                            'parsed_label_config': '{"tag": {...}}',
                            'evaluate_predictions_automatically': False,
                            'config_has_control_tags': True,
                            'skip_queue': 'REQUEUE_FOR_ME',
                            'reveal_preannotations_interactively': True,
                            'pinned_at': '2023-08-24T14:15:22Z',
                            'finished_task_number': 10,
                            'queue_total': 10,
                            'queue_done': 100,
                        },
                        media_type='application/json',
                    )
                ],
            )
        },
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Delete project',
        description='Delete a project by specified project ID.',
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Update project',
        description='Update the project settings for a specific project.',
        request=ProjectSerializer,
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
class ProjectAPI(generics.RetrieveUpdateDestroyAPIView):
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    queryset = Project.objects.with_counts()
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        DELETE=all_permissions.projects_delete,
        PATCH=all_permissions.projects_change,
        PUT=all_permissions.projects_change,
        POST=all_permissions.projects_create,
    )
    serializer_class = ProjectSerializer

    redirect_route = 'projects:project-detail'
    redirect_kwarg = 'pk'

    def get_queryset(self):
        serializer = GetFieldsSerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data.get('include')
        projects = Project.objects.with_counts(fields=fields).filter(
            organization=self.request.user.active_organization
        )

        # Only annotate FSM state for UI/API consumption when both feature flags are enabled
        if flag_set('fflag_feat_fit_568_finite_state_management', user=self.request.user) and flag_set(
            'fflag_feat_fit_710_fsm_state_fields', user=self.request.user
        ):
            projects = projects.with_state()

        return projects

    def get(self, request, *args, **kwargs):
        return super(ProjectAPI, self).get(request, *args, **kwargs)

    @api_webhook_for_delete(WebhookAction.PROJECT_DELETED)
    def delete(self, request, *args, **kwargs):
        return super(ProjectAPI, self).delete(request, *args, **kwargs)

    @api_webhook(WebhookAction.PROJECT_UPDATED)
    def patch(self, request, *args, **kwargs):
        project = self.get_object()
        label_config = self.request.data.get('label_config')

        # config changes can break view, so we need to reset them
        if label_config:
            try:
                _has_changes = config_essential_data_has_changed(label_config, project.label_config)
            except KeyError:
                pass

        return super(ProjectAPI, self).patch(request, *args, **kwargs)

    def perform_destroy(self, instance):
        # we don't need to relaculate counters if we delete whole project
        with temporary_disconnect_all_signals():
            instance.delete()

    @extend_schema(exclude=True)
    @api_webhook(WebhookAction.PROJECT_UPDATED)
    def put(self, request, *args, **kwargs):
        return super(ProjectAPI, self).put(request, *args, **kwargs)


# @method_decorator(
#     name='get',
#     decorator=extend_schema(
#         tags=['Projects'],
#         summary='Get next task to label',
#         description="""
#     Get the next task for labeling. If you enable Machine Learning in
#     your project, the response might include a "predictions"
#     field. It contains a machine learning prediction result for
#     this task.
#     """,
#         responses={200: TaskWithAnnotationsAndPredictionsAndDraftsSerializer()},
#     ),
# )
# leaving this method decorator info in case we put it back in swagger API docs
@extend_schema(exclude=True)
class ProjectNextTaskAPI(generics.RetrieveAPIView):
    permission_required = all_permissions.tasks_view
    serializer_class = TaskWithAnnotationsAndPredictionsAndDraftsSerializer
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        dm_queue = filters_ordering_selected_items_exist(request.data)
        prepared_tasks = get_prepared_queryset(request, project)

        assigned_flag = is_assignment_enforced_for_user(project, request.user)
        next_task, queue_info = get_next_task(request.user, prepared_tasks, project, dm_queue, assigned_flag)

        if next_task is None:
            raise NotFound(f'There are no tasks for {request.user}')

        # serialize task
        context = {'request': request, 'project': project, 'resolve_uri': True, 'annotations': False}
        serializer = NextTaskSerializer(next_task, context=context)
        response = serializer.data

        response['queue'] = queue_info
        return Response(response)


@extend_schema(exclude=True)
class LabelStreamHistoryAPI(generics.RetrieveAPIView):
    permission_required = all_permissions.tasks_view
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = self.get_object()

        history = get_label_stream_history(request.user, project)

        return Response(history)


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Validate label config',
        description='Validate an arbitrary labeling configuration.',
        responses={
            204: OpenApiResponse(description='Validation success'),
            400: OpenApiResponse(description='Validation failed'),
        },
        request=ProjectLabelConfigSerializer,
        extensions={
            'x-fern-audiences': ['internal'],
        },
    ),
)
class LabelConfigValidateAPI(generics.CreateAPIView):
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    permission_classes = (AllowAny,)
    serializer_class = ProjectLabelConfigSerializer

    def post(self, request, *args, **kwargs):
        return super(LabelConfigValidateAPI, self).post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except RestValidationError as exc:
            context = self.get_exception_handler_context()
            response = exception_handler(exc, context)
            response = self.finalize_response(request, response)
            return response

        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Projects'],
        operation_id='api_projects_validate_label_config',
        summary='Validate project label config',
        description='Determine whether the label configuration for a specific project is valid.',
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location='path',
                description='A unique integer value identifying this project.',
            ),
        ],
        request=ProjectLabelConfigSerializer,
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'validate_label_config',
            'x-fern-audiences': ['public'],
        },
    ),
)
class ProjectLabelConfigValidateAPI(generics.RetrieveAPIView):
    """Validate label config"""

    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ProjectLabelConfigSerializer
    permission_required = all_permissions.projects_change
    queryset = Project.objects.all()

    def post(self, request, *args, **kwargs):
        project = self.get_object()
        label_config = self.request.data.get('label_config')
        if not label_config:
            raise RestValidationError('Label config is not set or is empty')

        # check new config includes meaningful changes
        has_changed = config_essential_data_has_changed(label_config, project.label_config)
        project.validate_config(label_config, strict=True)
        return Response({'config_essential_data_has_changed': has_changed}, status=status.HTTP_200_OK)

    @extend_schema(exclude=True)
    def get(self, request, *args, **kwargs):
        return super(ProjectLabelConfigValidateAPI, self).get(request, *args, **kwargs)


class ProjectSummaryAPI(generics.RetrieveAPIView):
    parser_classes = (JSONParser,)
    serializer_class = ProjectSummarySerializer
    permission_required = all_permissions.projects_view
    queryset = ProjectSummary.objects.all()

    @extend_schema(exclude=True)
    def get(self, *args, **kwargs):
        return super(ProjectSummaryAPI, self).get(*args, **kwargs)


class ProjectSummaryResetAPI(GetParentObjectMixin, generics.CreateAPIView):
    """This API is useful when we need to reset project.summary.created_labels and created_labels_drafts
    and recalculate them from scratch. It's hard to correctly follow all changes in annotation region
    labels and these fields aren't calculated properly after some time. Label config changes are not allowed
    when these changes touch any labels from these created_labels* dictionaries.
    """

    parser_classes = (JSONParser,)
    parent_queryset = Project.objects.all()
    permission_required = ViewClassPermission(
        POST=all_permissions.projects_reset_cache,
    )

    @extend_schema(exclude=True)
    def post(self, *args, **kwargs):
        project = self.parent_object
        summary = project.summary
        start_job_async_or_sync(
            recalculate_created_annotations_and_labels_from_scratch,
            project,
            summary,
            organization_id=self.request.user.active_organization.id,
        )
        return Response(status=status.HTTP_200_OK)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Get project import status ',
        description="""
            Poll the status of an asynchronous project import operation.
            
            **Usage:**
            1. When you POST to `/api/projects/{project_id}/import`, you'll receive a response like `{"import": <import_id>}`
            2. Use that `import_id` with this GET endpoint to check the import status
            3. Poll this endpoint to see if the import has completed, is still processing, or has failed
            4. **Import errors and failures will only be visible in this GET response**, not in the original POST request
            
            This endpoint returns detailed information about the import including task counts, status, and any error messages.
        """,
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location='path',
                description='A unique integer value identifying this project import.',
            ),
        ],
        extensions={
            'x-fern-sdk-group-name': 'tasks',
            'x-fern-sdk-method-name': 'create_many_status',
            'x-fern-audiences': ['public'],
        },
    ),
)
class ProjectImportAPI(generics.RetrieveAPIView):
    permission_required = all_permissions.projects_change
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [ProjectImportPermission]
    parser_classes = (JSONParser,)
    serializer_class = ProjectImportSerializer
    queryset = ProjectImport.objects.all()
    lookup_url_kwarg = 'import_pk'


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Get project reimport status',
        description="""
            Poll the status of an asynchronous project reimport operation.
            
            **Usage:**
            1. When you POST to reimport tasks, you'll receive a response with a reimport ID
            2. Use that `reimport_id` with this GET endpoint to check the reimport status
            3. Poll this endpoint to see if the reimport has completed, is still processing, or has failed
            4. **Reimport errors and failures will only be visible in this GET response**, not in the original POST request
            
            This endpoint returns detailed information about the reimport including task counts, status, and any error messages.
        """,
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location='path',
                description='A unique integer value identifying this project reimport.',
            ),
        ],
        extensions={
            'x-fern-audiences': ['internal'],
        },
    ),
)
class ProjectReimportAPI(generics.RetrieveAPIView):
    permission_required = all_permissions.projects_change
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [ProjectImportPermission]
    parser_classes = (JSONParser,)
    serializer_class = ProjectReimportSerializer
    queryset = ProjectReimport.objects.all()
    lookup_url_kwarg = 'reimport_pk'


@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Delete all tasks',
        description='Delete all tasks from a specific project.',
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location='path',
                description='A unique integer value identifying this project.',
            ),
        ],
        extensions={
            'x-fern-sdk-group-name': 'tasks',
            'x-fern-sdk-method-name': 'delete_all_tasks',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],  # TODO: deprecate this endpoint in favor of tasks:tasks-list
        summary='List project tasks',
        description="""
            Retrieve a paginated list of tasks for a specific project. For example, use the following cURL command:
            ```bash
            curl -X GET {}/api/projects/{{id}}/tasks/?page=1&page_size=10 -H 'Authorization: Token abc123'
            ```
        """.format(
            settings.HOSTNAME or 'https://localhost:8080'
        ),
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location='path',
                description='A unique integer value identifying this project.',
            ),
        ]
        + paginator_help('tasks', 'Projects')['parameters'],
        extensions={
            'x-fern-audiences': ['internal'],  # TODO: deprecate this endpoint in favor of tasks:tasks-list
        },
    ),
)
class ProjectTaskListAPI(GetParentObjectMixin, generics.ListCreateAPIView, generics.DestroyAPIView):
    parser_classes = (JSONParser, FormParser)
    queryset = Task.objects.all()
    parent_queryset = Project.objects.all()
    permission_required = ViewClassPermission(
        GET=all_permissions.tasks_view,
        POST=all_permissions.tasks_change,
        DELETE=all_permissions.tasks_delete,
    )
    serializer_class = TaskSerializer
    redirect_route = 'projects:project-settings'
    redirect_kwarg = 'pk'

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return TaskSimpleSerializer
        else:
            return TaskSerializer

    def filter_queryset(self, queryset):
        project = generics.get_object_or_404(Project.objects.for_user(self.request.user), pk=self.kwargs.get('pk', 0))
        # ordering is deprecated here
        tasks = Task.objects.filter(project=project).order_by('-updated_at')
        if self.request.method == 'GET':
            from tasks.assignment import filter_tasks_for_user_assignments

            tasks, _ = filter_tasks_for_user_assignments(tasks, project, self.request.user)
        page = paginator(tasks, self.request)
        if page:
            return page
        else:
            raise Http404

    def delete(self, request, *args, **kwargs):
        project = generics.get_object_or_404(Project.objects.for_user(self.request.user), pk=self.kwargs['pk'])
        task_ids = list(Task.objects.filter(project=project).values('id'))
        Task.delete_tasks_without_signals(Task.objects.filter(project=project))
        logger.info(f'calling reset project_id={project.id} ProjectTaskListAPI.delete()')
        project.summary.reset()
        emit_webhooks_for_instance(request.user.active_organization, None, WebhookAction.TASKS_DELETED, task_ids)
        return Response(status=204)

    def get(self, *args, **kwargs):
        return super(ProjectTaskListAPI, self).get(*args, **kwargs)

    @extend_schema(exclude=True)
    def post(self, *args, **kwargs):
        return super(ProjectTaskListAPI, self).post(*args, **kwargs)

    def get_serializer_context(self):
        context = super(ProjectTaskListAPI, self).get_serializer_context()
        context['project'] = self.parent_object
        return context

    def perform_create(self, serializer):
        project = self.parent_object
        instance = serializer.save(project=project)
        emit_webhooks_for_instance(
            self.request.user.active_organization, project, WebhookAction.TASKS_CREATED, [instance]
        )
        return instance


def read_templates_and_groups():
    annotation_templates_dir = find_dir('annotation_templates')
    configs = []
    for config_file in pathlib.Path(annotation_templates_dir).glob('**/*.yml'):
        config = read_yaml(config_file)

        if settings.VERSION_EDITION != 'Community':
            if config.get('group', '').lower() == 'community contributions':
                continue

        if config.get('image', '').startswith('/static') and settings.HOSTNAME:
            # if hostname set manually, create full image urls
            config['image'] = settings.HOSTNAME + config['image']
        configs.append(config)
    template_groups_file = find_file(os.path.join('annotation_templates', 'groups.txt'))
    with open(template_groups_file, encoding='utf-8') as f:
        groups = f.read().splitlines()

    if settings.VERSION_EDITION != 'Community':
        groups = [group for group in groups if group.lower() != 'community contributions']

    logger.debug(f'{len(configs)} templates found.')
    return {'templates': configs, 'groups': groups}


@extend_schema(exclude=True)
class TemplateListAPI(generics.ListAPIView):
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    permission_required = all_permissions.projects_view
    # load this once in memory for performance
    templates_and_groups = read_templates_and_groups()

    def list(self, request, *args, **kwargs):
        return Response(self.templates_and_groups)


@extend_schema(exclude=True)
class ProjectSampleTask(generics.RetrieveAPIView):
    parser_classes = (JSONParser,)
    queryset = Project.objects.all()
    permission_required = all_permissions.projects_view
    serializer_class = ProjectSerializer

    def post(self, request, *args, **kwargs):
        label_config = self.request.data.get('label_config')
        include_annotation_and_prediction = self.request.data.get('include_annotation_and_prediction', False)

        if not label_config:
            raise RestValidationError('Label config is not set or is empty')

        project = self.get_object()

        if include_annotation_and_prediction:
            try:
                label_interface = LabelInterface(label_config)
                complete_task = label_interface.generate_complete_sample_task(raise_on_failure=True)
                # set the annotation's user id to the current user instead of -1
                user_id = request.user.id
                for annotation in complete_task['annotations']:
                    annotation['completed_by'] = user_id
                return Response({'sample_task': complete_task}, status=200)
            except Exception as e:
                logger.error(
                    f'Error generating enhanced sample task, falling back to original method: {str(e)}. Label config: {label_config}'
                )
                # Fallback to project.get_sample_task if LabelInterface.generate_complete_sample_task failed
                return Response({'sample_task': project.get_sample_task(label_config)}, status=200)
        else:
            # Use the simple sample task generation method
            return Response({'sample_task': project.get_sample_task(label_config)}, status=200)


@extend_schema(exclude=True)
class ProjectModelVersions(generics.RetrieveAPIView):
    parser_classes = (JSONParser,)
    permission_required = all_permissions.projects_view

    def get_queryset(self):
        return Project.objects.filter(organization=self.request.user.active_organization)

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = ProjectModelVersionParamsSerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        extended = serializer.validated_data.get('extended', False)
        include_live_models = serializer.validated_data.get('include_live_models', False)
        limit = serializer.validated_data.get('limit', None)
        data = project.get_model_versions(with_counters=True, extended=extended, limit=limit)

        if extended:
            serializer_models = None
            serializer = ProjectModelVersionExtendedSerializer(data, many=True)

            if include_live_models:
                ml_models = project.get_ml_backends()
                serializer_models = MLBackendSerializer(ml_models, many=True)

            return Response({'static': serializer.data, 'live': serializer_models and serializer_models.data})
        else:
            return Response(data=data)

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        model_version = request.data.get('model_version', None)

        if not model_version:
            raise RestValidationError('model_version param is required')

        count = project.delete_predictions(model_version=model_version)

        return Response(data=count)


class ProjectOrganizationScopedMixin:
    def get_queryset(self):
        return Project.objects.for_user(self.request.user)


class CSVRenderer(BaseRenderer):
    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b''
        if isinstance(data, bytes):
            return data
        return str(data).encode(self.charset)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='List unique annotators for project',
        description='Return unique users who have submitted annotations in the specified project.',
        responses={
            200: OpenApiResponse(
                description='List of annotator users',
                response=UserSimpleSerializer(many=True),
            )
        },
        extensions={
            'x-fern-sdk-group-name': 'projects',
            'x-fern-sdk-method-name': 'list_unique_annotators',
            'x-fern-audiences': ['public'],
        },
    ),
)
class ProjectAnnotatorsAPI(ProjectOrganizationScopedMixin, generics.RetrieveAPIView):
    permission_required = all_permissions.projects_view
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        annotator_ids = list(
            Annotation.objects.filter(project=project, completed_by_id__isnull=False)
            .values_list('completed_by_id', flat=True)
            .distinct()
        )
        users = User.objects.filter(id__in=annotator_ids).prefetch_related('om_through').order_by('id')
        data = UserSimpleSerializer(users, many=True, context={'request': request}).data
        return Response(data)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='List task assignments for project',
        description='List manual task assignments for the project (project owner only).',
        parameters=[
            OpenApiParameter(name='assignee', type=OpenApiTypes.INT, location='query', required=False),
            OpenApiParameter(name='task_id', type=OpenApiTypes.INT, location='query', required=False),
        ],
        responses={
            200: OpenApiResponse(
                description='List of task assignments with members and can_manage flag',
            )
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Assign tasks to annotators',
        description=(
            'Batch assign or unassign tasks to one or more annotators (project owner only). '
            'A task can hold several assignments at once (cross-validation labeling); '
            'users assigned but missing from assignees are unassigned.'
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'assignees': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'User IDs to assign; empty list to unassign all',
                    },
                    'task_ids': {'type': 'array', 'items': {'type': 'integer'}},
                },
                'required': ['assignees', 'task_ids'],
            }
        },
        responses={
            200: OpenApiResponse(description='Assignment result with processed items count'),
        },
    ),
)
class ProjectAssignmentsAPI(ProjectOrganizationScopedMixin, generics.RetrieveAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        POST=all_permissions.projects_change,
    )
    queryset = Project.objects.all()

    @staticmethod
    def _serialize_user(user):
        if not user:
            return None
        full_name = user.get_full_name().strip()
        display = full_name or user.username or user.email or f'User {user.id}'
        return {
            'id': user.id,
            'display_name': display,
            'email': user.email,
        }

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        self.check_object_permissions(request, project)
        if not can_manage_assignments(project, request.user):
            raise PermissionDenied('Only project owner can view task assignments')

        queryset = TaskAssignment.objects.filter(task__project=project).select_related('task', 'user', 'assigned_by')

        assignee = request.GET.get('assignee')
        if assignee not in (None, ''):
            try:
                queryset = queryset.filter(user_id=int(assignee))
            except (TypeError, ValueError) as exc:
                raise RestValidationError({'assignee': 'Invalid assignee value'}) from exc

        task_id = request.GET.get('task_id')
        if task_id not in (None, ''):
            try:
                queryset = queryset.filter(task_id=int(task_id))
            except (TypeError, ValueError) as exc:
                raise RestValidationError({'task_id': 'Invalid task ID'}) from exc

        # Order by the latest assignment action time from the audit log (e.g. reassignment),
        # rather than TaskAssignment.created_at which records the first assignment.
        latest_action = (
            TaskAssignmentAuditLog.objects.filter(task_id=OuterRef('task_id'))
            .order_by('-created_at', '-id')
            .values('created_at')[:1]
        )
        queryset = queryset.annotate(
            # Coalesce with created_at so audit-log-less rows sort by their (first) assignment time
            # instead of NULLs-first on Postgres.
            latest_assigned_at=Coalesce(Subquery(latest_action), F('created_at'))
        ).order_by('-latest_assigned_at', '-id')
        page = paginator(queryset, request)
        page_queryset = page if page is not None else queryset[:100]

        results = [
            {
                'task_id': assignment.task_id,
                'task_inner_id': assignment.task.inner_id,
                'assignee': self._serialize_user(assignment.user),
                'assigned_by': self._serialize_user(assignment.assigned_by),
                'assigned_at': assignment.latest_assigned_at or assignment.created_at,
            }
            for assignment in page_queryset
        ]

        members = [
            {
                'id': member.id,
                'display_name': (member.get_full_name().strip() or member.username or member.email or f'User {member.id}'),
                'email': member.email,
            }
            for member in get_assignable_users(project)
        ]

        return Response(
            {
                'results': results,
                'count': queryset.count(),
                'members': members,
                'can_manage': can_manage_assignments(project, request.user),
            }
        )

    def post(self, request, *args, **kwargs):
        project = self.get_object()
        self.check_object_permissions(request, project)

        if not can_manage_assignments(project, request.user):
            raise PermissionDenied('Only project owner can manage task assignment')

        raw_assignees = request.data.get('assignees')
        if raw_assignees is None:
            # Backward compatibility: single-assignee payload from older clients.
            legacy = request.data.get('assignee')
            if legacy in (None, ''):
                raise RestValidationError({'assignees': 'Assignees are required'})
            raw_assignees = [legacy]
        if not isinstance(raw_assignees, list):
            raise RestValidationError({'assignees': 'assignees must be a list of user IDs'})

        assignee_ids = []
        for raw in raw_assignees:
            if raw in (None, ''):
                continue
            try:
                uid = int(raw)
            except (TypeError, ValueError) as exc:
                raise RestValidationError({'assignees': 'Invalid assignee value'}) from exc
            if uid != 0 and uid not in assignee_ids:
                assignee_ids.append(uid)

        task_ids = request.data.get('task_ids') or []
        if not isinstance(task_ids, list):
            raise RestValidationError({'task_ids': 'task_ids must be a list'})

        parsed_task_ids = []
        for task_id in task_ids:
            try:
                parsed_task_ids.append(int(task_id))
            except (TypeError, ValueError):
                continue

        if not parsed_task_ids:
            return Response({'processed_items': 0, 'detail': 'No tasks selected'})

        if assignee_ids:
            valid_ids = set(get_assignable_users(project).values_list('id', flat=True))
            invalid = [uid for uid in assignee_ids if uid not in valid_ids]
            if invalid:
                raise RestValidationError({'assignees': 'Selected user is not in this organization'})

        stats = apply_task_assignments(project, parsed_task_ids, assignee_ids, request.user)

        if not assignee_ids:
            detail = f'Unassigned {stats["removed"]} tasks'
        else:
            detail = f'Assigned {stats["assigned"]} task assignments'

        return Response({'processed_items': stats['changed'], 'detail': detail})


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='List assignment audit log',
        description='List task assignment audit log entries for the project (project owner only).',
        parameters=[
            OpenApiParameter(name='task_id', type=OpenApiTypes.INT, location='query', required=False),
            OpenApiParameter(
                name='action',
                type=OpenApiTypes.STR,
                location='query',
                required=False,
                description='assigned | reassigned | unassigned',
            ),
        ],
        responses={
            200: OpenApiResponse(description='List of assignment audit log entries'),
        },
    ),
)
class ProjectAssignmentAuditLogAPI(ProjectOrganizationScopedMixin, generics.RetrieveAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
    )
    queryset = Project.objects.all()

    @staticmethod
    def _serialize_user(user):
        if not user:
            return None
        full_name = user.get_full_name().strip()
        display = full_name or user.username or user.email or f'User {user.id}'
        return {
            'id': user.id,
            'display_name': display,
            'email': user.email,
        }

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        self.check_object_permissions(request, project)
        if not can_manage_assignments(project, request.user):
            raise PermissionDenied('Only project owner can view assignment audit logs')

        queryset = TaskAssignmentAuditLog.objects.filter(project=project).select_related(
            'task', 'assignee', 'previous_assignee', 'assigned_by'
        )

        task_id = request.GET.get('task_id')
        if task_id not in (None, ''):
            try:
                queryset = queryset.filter(task_id=int(task_id))
            except (TypeError, ValueError) as exc:
                raise RestValidationError({'task_id': 'Invalid task ID'}) from exc

        action = request.GET.get('action')
        if action in {
            TaskAssignmentAuditLog.ACTION_ASSIGNED,
            TaskAssignmentAuditLog.ACTION_REASSIGNED,
            TaskAssignmentAuditLog.ACTION_UNASSIGNED,
        }:
            queryset = queryset.filter(action=action)

        queryset = queryset.order_by('-created_at')
        page = paginator(queryset, request)
        page_queryset = page if page is not None else queryset[:100]

        results = [
            {
                'id': item.id,
                'task_id': item.task_id,
                'task_inner_id': item.task.inner_id,
                'action': item.action,
                'assignee': self._serialize_user(item.assignee),
                'previous_assignee': self._serialize_user(item.previous_assignee),
                'assigned_by': self._serialize_user(item.assigned_by),
                'created_at': item.created_at,
            }
            for item in page_queryset
        ]

        return Response({'results': results, 'count': queryset.count()})


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='List workflow audit log',
        description='List annotation workflow audit log entries (submitted/skipped/updated) for the project (project owner only).',
        parameters=[
            OpenApiParameter(
                name='action',
                type=OpenApiTypes.STR,
                location='query',
                required=False,
                description='submitted | skipped | updated',
            ),
            OpenApiParameter(name='actor_id', type=OpenApiTypes.INT, location='query', required=False),
            OpenApiParameter(name='date_from', type=OpenApiTypes.DATE, location='query', required=False),
            OpenApiParameter(name='date_to', type=OpenApiTypes.DATE, location='query', required=False),
            OpenApiParameter(name='format', type=OpenApiTypes.STR, location='query', required=False, description='csv'),
        ],
        responses={
            200: OpenApiResponse(description='List of workflow audit log entries'),
        },
    ),
)
class ProjectWorkflowAuditLogAPI(ProjectOrganizationScopedMixin, generics.RetrieveAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
    )
    queryset = Project.objects.all()
    renderer_classes = [JSONRenderer, CSVRenderer]

    @staticmethod
    def _serialize_user(user):
        if not user:
            return None
        full_name = user.get_full_name().strip()
        display = full_name or user.username or user.email or f'User {user.id}'
        return {
            'id': user.id,
            'display_name': display,
            'email': user.email,
        }

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        self.check_object_permissions(request, project)
        if not can_manage_assignments(project, request.user):
            raise PermissionDenied('Only project owner can view workflow audit logs')

        queryset = TaskWorkflowAuditLog.objects.filter(project=project).select_related('task', 'actor')

        action = request.GET.get('action')
        if action in {
            TaskWorkflowAuditLog.ACTION_SUBMITTED,
            TaskWorkflowAuditLog.ACTION_SKIPPED,
            TaskWorkflowAuditLog.ACTION_UPDATED,
        }:
            queryset = queryset.filter(action=action)

        actor_id = request.GET.get('actor_id')
        if actor_id not in (None, ''):
            try:
                queryset = queryset.filter(actor_id=int(actor_id))
            except (TypeError, ValueError):
                pass

        date_from = request.GET.get('date_from')
        if date_from:
            parsed_date_from = parse_date(date_from)
            if parsed_date_from:
                queryset = queryset.filter(created_at__date__gte=parsed_date_from)

        date_to = request.GET.get('date_to')
        if date_to:
            parsed_date_to = parse_date(date_to)
            if parsed_date_to:
                queryset = queryset.filter(created_at__date__lte=parsed_date_to)

        queryset = queryset.order_by('-created_at')

        if request.GET.get('format') == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = (
                f'attachment; filename="project_{project.id}_workflow_audit.csv"'
            )
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow(['task_id', 'task_inner_id', 'action', 'actor', 'created_at'])

            for item in queryset:
                actor_display = ''
                if item.actor:
                    actor_display = item.actor.get_full_name().strip() or item.actor.username or item.actor.email or str(item.actor_id)

                writer.writerow(
                    [
                        item.task_id,
                        item.task.inner_id,
                        item.action,
                        actor_display,
                        item.created_at.isoformat() if item.created_at else '',
                    ]
                )

            return response

        page = paginator(queryset, request)
        page_queryset = page if page is not None else queryset[:100]

        results = [
            {
                'id': item.id,
                'task_id': item.task_id,
                'task_inner_id': item.task.inner_id,
                'action': item.action,
                'actor': self._serialize_user(item.actor),
                'created_at': item.created_at,
            }
            for item in page_queryset
        ]

        members = [
            {
                'id': member.id,
                'display_name': (member.get_full_name().strip() or member.username or member.email or f'User {member.id}'),
                'email': member.email,
            }
            for member in get_assignable_users(project)
        ]

        return Response({'results': results, 'count': queryset.count(), 'members': members})


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Projects'],
        summary='Get project statistics',
        description='Aggregated project statistics: overview, assignment coverage, workflow rates, activity trend and annotator performance (project owner only).',
        responses={
            200: OpenApiResponse(description='Project statistics'),
        },
    ),
)
class ProjectStatisticsAPI(ProjectOrganizationScopedMixin, generics.RetrieveAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
    )
    queryset = Project.objects.all()

    @staticmethod
    def _serialize_user(user):
        if not user:
            return None
        full_name = user.get_full_name().strip()
        display = full_name or user.username or user.email or f'User {user.id}'
        return {
            'id': user.id,
            'display_name': display,
            'email': user.email,
        }

    @staticmethod
    def _safe_rate(numerator, denominator):
        if not denominator:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    @staticmethod
    def _safe_avg(values):
        values = [value for value in values if value is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    @staticmethod
    def _format_seconds(seconds):
        if seconds is None:
            return None
        total = max(float(seconds), 0.0)
        minutes = int(total // 60)
        secs = int(round(total % 60))
        if minutes and secs == 60:
            minutes += 1
            secs = 0
        if minutes:
            return f'{minutes}m {secs}s'
        return f'{secs}s'

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        self.check_object_permissions(request, project)
        if not can_manage_assignments(project, request.user):
            raise PermissionDenied('Only project owner can view project statistics')

        tasks_qs = Task.objects.filter(project=project)
        total_tasks = tasks_qs.count()
        completed_tasks = tasks_qs.filter(is_labeled=True).count()
        pending_tasks = max(total_tasks - completed_tasks, 0)

        # A task can hold several assignments (cross-validation); count tasks, not assignment rows.
        assigned_tasks = (
            TaskAssignment.objects.filter(task__project=project).values('task_id').distinct().count()
        )
        unassigned_tasks = max(total_tasks - assigned_tasks, 0)
        assignment_coverage = self._safe_rate(assigned_tasks, total_tasks)

        workflow_qs = TaskWorkflowAuditLog.objects.filter(project=project)
        submitted_count = workflow_qs.filter(action=TaskWorkflowAuditLog.ACTION_SUBMITTED).count()
        skipped_count = workflow_qs.filter(action=TaskWorkflowAuditLog.ACTION_SKIPPED).count()
        updated_count = workflow_qs.filter(action=TaskWorkflowAuditLog.ACTION_UPDATED).count()

        total_workflow_events = submitted_count + skipped_count
        skip_rate = self._safe_rate(skipped_count, total_workflow_events)

        today = timezone.localdate()
        date_from = today - timedelta(days=6)
        activity_daily_qs = (
            workflow_qs.filter(
                action__in=(TaskWorkflowAuditLog.ACTION_SUBMITTED, TaskWorkflowAuditLog.ACTION_UPDATED),
                created_at__date__gte=date_from,
                created_at__date__lte=today,
            )
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        daily_map = {item['day']: item['count'] for item in activity_daily_qs}
        completion_trend = []
        for day_offset in range(7):
            day = date_from + timedelta(days=day_offset)
            completion_trend.append(
                {
                    'date': day.isoformat(),
                    'count': daily_map.get(day, 0),
                }
            )

        today_completed = daily_map.get(today, 0)

        # lead_time is overwritten on update; attribute it to the last updater, otherwise author.
        lead_time_rows = list(
            Annotation.objects.filter(
                project=project,
                was_cancelled=False,
                lead_time__isnull=False,
            ).values('id', 'lead_time', 'completed_by_id', 'updated_by_id')
        )
        lead_time_by_annotation_id = {item['id']: item['lead_time'] for item in lead_time_rows}
        avg_lead_time = self._safe_avg(lead_time_by_annotation_id.values())

        lead_times_by_actor = {}
        for item in lead_time_rows:
            owner_id = item['updated_by_id'] or item['completed_by_id']
            if not owner_id:
                continue
            lead_times_by_actor.setdefault(owner_id, []).append(item['lead_time'])

        # Pre-annotation imports set completed_by to the importer; member work is mostly
        # ACTION_UPDATED. Credit annotators for distinct annotations they authored or updated.
        completed_annotation_ids_by_actor = {}
        for item in (
            Annotation.objects.filter(
                project=project,
                was_cancelled=False,
                completed_by_id__isnull=False,
            )
            .values('completed_by_id', 'id')
        ):
            completed_annotation_ids_by_actor.setdefault(item['completed_by_id'], set()).add(item['id'])

        updated_annotation_ids_by_actor = {}
        for item in (
            workflow_qs.filter(
                action=TaskWorkflowAuditLog.ACTION_UPDATED,
                actor_id__isnull=False,
                annotation_id__isnull=False,
            ).values('actor_id', 'annotation_id')
        ):
            updated_annotation_ids_by_actor.setdefault(item['actor_id'], set()).add(item['annotation_id'])

        workflow_by_actor = {
            item['actor_id']: {
                'skipped': item['skipped'],
                'updated': item['updated'],
            }
            for item in workflow_qs.filter(actor_id__isnull=False)
            .values('actor_id')
            .annotate(
                skipped=Count('id', filter=Q(action=TaskWorkflowAuditLog.ACTION_SKIPPED)),
                updated=Count('id', filter=Q(action=TaskWorkflowAuditLog.ACTION_UPDATED)),
            )
        }

        actor_ids = (
            set(completed_annotation_ids_by_actor.keys())
            | set(updated_annotation_ids_by_actor.keys())
            | set(workflow_by_actor.keys())
            | set(lead_times_by_actor.keys())
        )
        users_by_id = User.objects.in_bulk(actor_ids)

        annotator_stats = []
        for actor_id in actor_ids:
            user = users_by_id.get(actor_id)
            credited_annotation_ids = (
                completed_annotation_ids_by_actor.get(actor_id, set())
                | updated_annotation_ids_by_actor.get(actor_id, set())
            )
            completed = len(credited_annotation_ids)
            skipped = workflow_by_actor.get(actor_id, {}).get('skipped', 0)
            updated = workflow_by_actor.get(actor_id, {}).get('updated', 0)
            handled = completed + skipped
            actor_avg_lead_time = self._safe_avg(lead_times_by_actor.get(actor_id, []))
            annotator_stats.append(
                {
                    'actor': self._serialize_user(user),
                    'completed': completed,
                    'skipped': skipped,
                    'updated': updated,
                    'avg_lead_time': actor_avg_lead_time,
                    'avg_lead_time_display': self._format_seconds(actor_avg_lead_time),
                    'skip_rate': self._safe_rate(skipped, handled),
                }
            )

        annotator_stats.sort(
            key=lambda item: (
                -item['completed'],
                item['skip_rate'],
                item['actor']['display_name'] if item['actor'] else '',
            )
        )

        return Response(
            {
                'overview': {
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'pending_tasks': pending_tasks,
                    'completion_rate': self._safe_rate(completed_tasks, total_tasks),
                    'avg_lead_time': avg_lead_time,
                    'avg_lead_time_display': self._format_seconds(avg_lead_time),
                },
                'assignment': {
                    'assigned_tasks': assigned_tasks,
                    'unassigned_tasks': unassigned_tasks,
                    'coverage_rate': assignment_coverage,
                },
                'workflow': {
                    'submitted_count': submitted_count,
                    'skipped_count': skipped_count,
                    'updated_count': updated_count,
                    'skip_rate': skip_rate,
                },
                'activity': {
                    'today_completed': today_completed,
                    'completion_trend': completion_trend,
                },
                'annotators': annotator_stats,
            }
        )
