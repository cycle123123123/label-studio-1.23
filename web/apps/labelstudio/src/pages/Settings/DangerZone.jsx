import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import i18next from "i18next";
import { useHistory } from "react-router";
import { Button, Typography, useToast } from "@humansignal/ui";
import { useUpdatePageTitle, createTitleFromSegments } from "@humansignal/core";
import { Label } from "../../components/Form";
import { modal } from "../../components/Modal/Modal";
import { useModalControls } from "../../components/Modal/ModalPopup";
import Input from "../../components/Form/Elements/Input/Input";
import { Space } from "../../components/Space/Space";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { useProject } from "../../providers/ProjectProvider";
import { cn } from "../../utils/bem";

export const DangerZone = () => {
  const { t } = useTranslation();
  const { project } = useProject();
  const api = useAPI();
  const history = useHistory();
  const toast = useToast();
  const [processing, setProcessing] = useState(null);

  useUpdatePageTitle(createTitleFromSegments([project?.title, t("danger_zone.page_title", "Danger Zone")]));

  const showDangerConfirmation = ({ title, message, requiredWord, buttonText, onConfirm }) => {
    const isDev = process.env.NODE_ENV === "development";

    return modal({
      title,
      width: 600,
      allowClose: false,
      body: () => {
        const ctrl = useModalControls();
        const inputValue = ctrl?.state?.inputValue || "";

        return (
          <div>
            <Typography variant="body" size="medium" className="mb-tight">
              {message}
            </Typography>
            <Input
              label={t("danger_zone.confirm_label", {
                requiredWord,
                defaultValue: 'To proceed, type "{{requiredWord}}" in the field below:',
              })}
              value={inputValue}
              onChange={(e) => ctrl?.setState({ inputValue: e.target.value })}
              autoFocus
              data-testid="danger-zone-confirmation-input"
              autoComplete="off"
            />
          </div>
        );
      },
      footer: () => {
        const ctrl = useModalControls();
        const inputValue = (ctrl?.state?.inputValue || "").trim().toLowerCase();
        const isValid = isDev || inputValue === requiredWord.toLowerCase();

        return (
          <Space align="end">
            <Button
              variant="neutral"
              look="outline"
              onClick={() => ctrl?.hide()}
              data-testid="danger-zone-cancel-button"
            >
              {t("cancel", "Cancel")}
            </Button>
            <Button
              variant="negative"
              disabled={!isValid}
              onClick={async () => {
                await onConfirm();
                ctrl?.hide();
              }}
              data-testid="danger-zone-confirm-button"
            >
              {buttonText}
            </Button>
          </Space>
        );
      },
    });
  };

  const handleOnClick = (type) => () => {
    const actionConfig = {
      reset_cache: {
        title: t("danger_zone.reset_cache.title", "Reset Cache"),
        message: t("danger_zone.reset_cache.message", {
          projectName: project.title,
          defaultValue: 'You are about to reset the cache for project "{{projectName}}". This action cannot be undone.',
        }),
        requiredWord: t("danger_zone.reset_cache.required_word", "cache"),
        buttonText: t("danger_zone.reset_cache.button_text", "Reset Cache"),
      },
      tabs: {
        title: t("danger_zone.drop_tabs.title", "Drop All Tabs"),
        message: t("danger_zone.drop_tabs.message", {
          projectName: project.title,
          defaultValue: 'You are about to drop all tabs for project "{{projectName}}". This action cannot be undone.',
        }),
        requiredWord: t("danger_zone.drop_tabs.required_word", "tabs"),
        buttonText: t("danger_zone.drop_tabs.button_text", "Drop All Tabs"),
      },
      project: {
        title: t("danger_zone.delete_project.title", "Delete Project"),
        message: t("danger_zone.delete_project.message", {
          projectName: project.title,
          defaultValue: 'You are about to delete project "{{projectName}}". This action cannot be undone.',
        }),
        requiredWord: t("danger_zone.delete_project.required_word", "delete"),
        buttonText: t("danger_zone.delete_project.button_text", "Delete Project"),
      },
    };

    const config = actionConfig[type];

    if (!config) {
      return;
    }

    showDangerConfirmation({
      ...config,
      onConfirm: async () => {
        setProcessing(type);
        try {
          if (type === "reset_cache") {
            await api.callApi("projectResetCache", {
              params: {
                pk: project.id,
              },
            });
            toast.show({ message: t("danger_zone.reset_cache.success_message", "Cache reset successfully") });
          } else if (type === "tabs") {
            await api.callApi("deleteTabs", {
              body: {
                project: project.id,
              },
            });
            toast.show({ message: t("danger_zone.drop_tabs.success_message", "All tabs dropped successfully") });
          } else if (type === "project") {
            await api.callApi("deleteProject", {
              params: {
                pk: project.id,
              },
            });
            toast.show({ message: t("danger_zone.delete_project.success_message", "Project deleted successfully") });
            history.replace("/projects");
          }
        } catch (error) {
          toast.show({
            message: t("common.error_message", {
              message: error.message,
              defaultValue: "Error: {{message}}",
            }),
            type: "error",
          });
        } finally {
          setProcessing(null);
        }
      },
    });
  };

  const buttons = useMemo(
    () => [
      {
        type: "annotations",
        disabled: true, //&& !project.total_annotations_number,
        label: `Delete ${project.total_annotations_number} Annotations`,
      },
      {
        type: "tasks",
        disabled: true, //&& !project.task_number,
        label: `Delete ${project.task_number} Tasks`,
      },
      {
        type: "predictions",
        disabled: true, //&& !project.total_predictions_number,
        label: `Delete ${project.total_predictions_number} Predictions`,
      },
      {
        type: "reset_cache",
        help: t(
          "danger_zone.reset_cache.help",
          "Reset Cache may help in cases like if you are unable to modify the labeling configuration due to validation errors concerning existing labels, but you are confident that the labels don't exist. You can use this action to reset the cache and try again.",
        ),
        label: t("danger_zone.reset_cache.button_text", "Reset Cache"),
      },
      {
        type: "tabs",
        help: t(
          "danger_zone.drop_tabs.help",
          "If the Data Manager is not loading, dropping all Data Manager tabs can help.",
        ),
        label: t("danger_zone.drop_tabs.button_text", "Drop All Tabs"),
      },
      {
        type: "project",
        help: t(
          "danger_zone.delete_project.help",
          "Deleting a project removes all tasks, annotations, and project data from the database.",
        ),
        label: t("danger_zone.delete_project.button_text", "Delete Project"),
      },
    ],
    [project, t],
  );

  return (
    <div className={cn("simple-settings").toClassName()}>
      <Typography variant="headline" size="medium" className="mb-tighter">
        {t("danger_zone.section_title", "Danger Zone")}
      </Typography>
      <Typography variant="body" size="medium" className="text-neutral-content-subtler !mb-base">
        {t(
          "danger_zone.description",
          "Perform these actions at your own risk. Actions you take on this page can't be reverted. Make sure your data is backed up.",
        )}
      </Typography>

      {project.id ? (
        <div style={{ marginTop: 16 }}>
          {buttons.map((btn) => {
            const waiting = processing === btn.type;
            const disabled = btn.disabled || (processing && !waiting);

            return (
              btn.disabled !== true && (
                <div className={cn("settings-wrapper").toClassName()} key={btn.type}>
                  <Typography variant="title" size="large">
                    {btn.label}
                  </Typography>
                  {btn.help && <Label description={btn.help} style={{ width: 600, display: "block" }} />}
                  <Button
                    key={btn.type}
                    variant="negative"
                    look="outlined"
                    disabled={disabled}
                    waiting={waiting}
                    onClick={handleOnClick(btn.type)}
                    style={{ marginTop: 16 }}
                  >
                    {btn.label}
                  </Button>
                </div>
              )
            );
          })}
        </div>
      ) : (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 32 }}>
          <Spinner size={32} />
        </div>
      )}
    </div>
  );
};

DangerZone.title = i18next.t("danger_zone.menu_title", "Danger Zone");
DangerZone.path = "/danger-zone";
