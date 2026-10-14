import { Button } from "@humansignal/ui";
import i18next from "i18next";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAPI } from "../../providers/ApiProvider";
import { useProject } from "../../providers/ProjectProvider";
import { cn } from "../../utils/bem";
import { Pagination } from "../../components/Pagination/Pagination";
import { absoluteURL } from "../../utils/helpers";

const PAGE_SIZE = 50;
const MAX_RANGE_SPAN = 5000;

export const AssignmentSettings = () => {
  const { t } = useTranslation();
  const api = useAPI();
  const { project } = useProject();
  const [members, setMembers] = useState([]);
  const [canManage, setCanManage] = useState(false);
  const [assignees, setAssignees] = useState([]);
  const [memberFilter, setMemberFilter] = useState("");
  const [taskIdsInput, setTaskIdsInput] = useState("");
  const [assignments, setAssignments] = useState([]);
  const [assignmentCount, setAssignmentCount] = useState(0);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditCount, setAuditCount] = useState(0);
  const [assignmentPage, setAssignmentPage] = useState(1);
  const [auditPage, setAuditPage] = useState(1);
  const [assignmentLoading, setAssignmentLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [mutationLoading, setMutationLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [message, setMessage] = useState("");
  const assignmentRequestSequence = useRef(0);
  const auditRequestSequence = useRef(0);
  const loading = assignmentLoading || auditLoading || mutationLoading;

  // Accepts "12, 13, 20-30" style input (comma / space / semicolon separated,
  // ranges with - ~ 至), which makes bulk assignment of hundreds of tasks easy.
  const { taskIds: normalizedTaskIds, invalidTokens } = useMemo(() => {
    const ids = new Set();
    const invalid = [];
    const tokens = (taskIdsInput || "").split(/[\s,，;；]+/).filter(Boolean);

    for (const token of tokens) {
      const range = token.match(/^(\d+)\s*[-~至]\s*(\d+)$/);

      if (range) {
        const a = Number(range[1]);
        const b = Number(range[2]);
        const [start, end] = a <= b ? [a, b] : [b, a];

        if (end - start > MAX_RANGE_SPAN) {
          invalid.push(token);
          continue;
        }
        for (let id = start; id <= end; id += 1) ids.add(id);
        continue;
      }

      const value = Number(token);

      if (Number.isInteger(value) && value > 0) ids.add(value);
      else invalid.push(token);
    }

    return { taskIds: [...ids].sort((a, b) => a - b), invalidTokens: invalid };
  }, [taskIdsInput]);

  const actionDisplay = useCallback(
    (action) => t(`assignment_settings.action_${action}`, { defaultValue: action }),
    [t],
  );

  const fetchAssignments = useCallback(
    async (page) => {
      if (!project?.id) return;
      const requestId = ++assignmentRequestSequence.current;
      setAssignmentLoading(true);
      try {
        const response = await api.callApi("projectAssignments", {
          params: { pk: project.id, page, page_size: PAGE_SIZE },
        });
        if (!response || requestId !== assignmentRequestSequence.current) return;
        setAssignments(response?.results ?? []);
        setAssignmentCount(response?.count ?? 0);
        setMembers(response?.members ?? []);
        setCanManage(Boolean(response?.can_manage));
      } finally {
        if (requestId === assignmentRequestSequence.current) setAssignmentLoading(false);
      }
    },
    [api, project?.id],
  );

  const fetchAuditLogs = useCallback(
    async (page) => {
      if (!project?.id) return;
      const requestId = ++auditRequestSequence.current;
      setAuditLoading(true);
      try {
        const response = await api.callApi("projectAssignmentAudit", {
          params: { pk: project.id, page, page_size: PAGE_SIZE },
        });
        if (!response || requestId !== auditRequestSequence.current) return;
        setAuditLogs(response?.results ?? []);
        setAuditCount(response?.count ?? 0);
      } finally {
        if (requestId === auditRequestSequence.current) setAuditLoading(false);
      }
    },
    [api, project?.id],
  );

  useEffect(() => {
    fetchAssignments(assignmentPage);
  }, [assignmentPage, fetchAssignments, refreshVersion]);

  useEffect(() => {
    fetchAuditLogs(auditPage);
  }, [auditPage, fetchAuditLogs, refreshVersion]);

  const toggleAssignee = (memberId) => {
    setAssignees((current) =>
      current.includes(memberId) ? current.filter((id) => id !== memberId) : [...current, memberId],
    );
  };

  const filteredMembers = useMemo(() => {
    const needle = (memberFilter || "").trim().toLowerCase();

    if (!needle) return members;
    return members.filter((member) => (member.display_name || "").toLowerCase().includes(needle));
  }, [members, memberFilter]);

  const exportCsv = useCallback(
    (endpoint) => {
      if (!project?.id) return;
      window.open(absoluteURL(`/api/projects/${project.id}/${endpoint}/?format=csv`), "_blank", "noopener,noreferrer");
    },
    [project?.id],
  );

  const applyAssignment = async (nextAssignees = assignees) => {
    if (!project?.id || normalizedTaskIds.length === 0) return;

    setMutationLoading(true);
    setMessage("");
    try {
      const response = await api.callApi("updateProjectAssignments", {
        params: { pk: project.id },
        body: {
          assignees: nextAssignees,
          task_ids: normalizedTaskIds,
        },
      });
      if (!response?.$meta?.ok) return;

      setMessage(response?.detail ?? t("assignment_settings.operation_done", "Operation completed"));
      setTaskIdsInput("");
      setAssignmentPage(1);
      setAuditPage(1);
      setRefreshVersion((version) => version + 1);
    } finally {
      setMutationLoading(false);
    }
  };

  return (
    <div className={cn("assignment-settings").toClassName()}>
      <div className={cn("assignment-settings").elem("wrapper").toClassName()}>
        <h1>{t("assignment_settings.section_title", "Assignment Management")}</h1>

        <div className={cn("settings-wrapper").toClassName()}>
          <h3>{t("assignment_settings.bulk_title", "Bulk Assign / Unassign")}</h3>
          <p className="settings-description">
            {t(
              "assignment_settings.bulk_desc",
              "Input task IDs (comma / space separated, ranges allowed: 1-10), then tick the annotators to assign.",
            )}
          </p>

          <div className={cn("assignment-settings").elem("panel").toClassName()}>
            <div className={cn("assignment-settings").elem("field").toClassName()}>
              <label htmlFor="assignment-task-ids">
                {t("assignment_settings.task_ids_label", "Task IDs (DM “ID” column)")}
              </label>
              <input
                id="assignment-task-ids"
                type="text"
                value={taskIdsInput}
                onChange={(event) => setTaskIdsInput(event.target.value)}
                placeholder={t("assignment_settings.task_ids_placeholder", "e.g. 12, 13, 20-30")}
                disabled={!canManage || loading}
              />
              <p className={cn("assignment-settings").elem("hint").toClassName()}>
                {t("assignment_settings.task_ids_hint", "Ranges supported: 1-10, or mixed like 1,3,5-8")}
              </p>
              {normalizedTaskIds.length > 0 && (
                <p className={cn("assignment-settings").elem("hint").toClassName()}>
                  {t("assignment_settings.parsed_count", "Matched {{count}} tasks", {
                    count: normalizedTaskIds.length,
                  })}
                  {normalizedTaskIds.length <= 20 ? `: ${normalizedTaskIds.join(", ")}` : ""}
                </p>
              )}
              {invalidTokens.length > 0 && (
                <p className={cn("assignment-settings").elem("warning").toClassName()}>
                  {t("assignment_settings.invalid_tokens", "Ignored invalid input: {{tokens}}", {
                    tokens: invalidTokens.join(", "),
                  })}
                </p>
              )}
            </div>

            <div className={cn("assignment-settings").elem("field").toClassName()}>
              <label htmlFor="assignment-members">
                {t("assignment_settings.assignees_label", "Assignees (multi-select)")}
              </label>
              {members.length > 6 && (
                <input
                  type="search"
                  value={memberFilter}
                  onChange={(event) => setMemberFilter(event.target.value)}
                  placeholder={t("assignment_settings.member_filter_placeholder", "Filter members")}
                  disabled={loading}
                />
              )}
              <div
                className={cn("assignment-settings").elem("members").toClassName()}
                id="assignment-members"
                role="group"
              >
                {filteredMembers.map((member) => (
                  <label
                    key={member.id}
                    className={cn("assignment-settings").elem("member").toClassName()}
                    data-checked={assignees.includes(member.id)}
                  >
                    <input
                      type="checkbox"
                      checked={assignees.includes(member.id)}
                      onChange={() => toggleAssignee(member.id)}
                      disabled={!canManage || loading}
                    />
                    <span>{member.display_name}</span>
                  </label>
                ))}
                {filteredMembers.length === 0 && (
                  <p className={cn("assignment-settings").elem("hint").toClassName()}>
                    {t("assignment_settings.no_members", "No members found")}
                  </p>
                )}
              </div>
              <div className={cn("assignment-settings").elem("member_actions").toClassName()}>
                <button
                  type="button"
                  onClick={() => setAssignees(filteredMembers.map((member) => member.id))}
                  disabled={!canManage || loading}
                >
                  {t("assignment_settings.select_all", "Select all")}
                </button>
                <button type="button" onClick={() => setAssignees([])} disabled={!canManage || loading}>
                  {t("assignment_settings.clear_selection", "Clear")}
                </button>
                <span className={cn("assignment-settings").elem("hint").toClassName()}>
                  {t("assignment_settings.selected_count", "{{count}} selected", { count: assignees.length })}
                </span>
              </div>
            </div>

            <div className={cn("assignment-settings").elem("actions").toClassName()}>
              <Button
                onClick={() => applyAssignment(assignees)}
                disabled={!canManage || loading || normalizedTaskIds.length === 0 || assignees.length === 0}
                aria-label={t("assignment_settings.apply_aria", "Apply assignment")}
              >
                {t("assignment_settings.apply_to_selected", "Assign to {{count}} annotator(s)", {
                  count: assignees.length,
                })}
              </Button>
              <Button
                look="outlined"
                onClick={() => applyAssignment([])}
                disabled={!canManage || loading || normalizedTaskIds.length === 0 || assignees.length === 0}
                aria-label={t("assignment_settings.unassign_aria", "Unassign tasks")}
              >
                {t("assignment_settings.unassign", "Unassign these tasks")}
              </Button>
            </div>
          </div>

          {!canManage && (
            <p className="settings-description">
              {t("assignment_settings.permission_hint", "Only project owner can manage task assignment.")}
            </p>
          )}
          {message && <p className={cn("assignment-settings").elem("message").toClassName()}>{message}</p>}
        </div>

        <div className={cn("settings-wrapper").toClassName()}>
          <h3>
            {t("assignment_settings.current_title", "Current Assignment Records")} ({assignmentCount})
          </h3>
          <div className={cn("assignment-settings").elem("table_actions").toClassName()}>
            <Button look="outlined" onClick={() => exportCsv("assignments")} disabled={!project?.id || loading}>
              {t("assignment_settings.export_csv", "Export CSV")}
            </Button>
          </div>
          <table className={cn("assignment-settings").elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("assignment_settings.task_col", "Task")}</th>
                <th>{t("assignment_settings.assignee_col", "Assignee")}</th>
                <th>{t("assignment_settings.assigned_by_col", "Assigned By")}</th>
                <th>{t("assignment_settings.assigned_at_col", "Assigned At")}</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((item) => (
                <tr key={`${item.task_id}-${item?.assignee?.id ?? "none"}`}>
                  <td>#{item.task_id}</td>
                  <td>{item?.assignee?.display_name ?? "-"}</td>
                  <td>{item?.assigned_by?.display_name ?? "-"}</td>
                  <td>{item?.assigned_at ? new Date(item.assigned_at).toLocaleString() : "-"}</td>
                </tr>
              ))}
              {assignments.length === 0 && (
                <tr>
                  <td colSpan={4}>{t("assignment_settings.empty", "No records")}</td>
                </tr>
              )}
            </tbody>
          </table>
          <Pagination
            name="project-assignment-records"
            label={t("assignment_settings.current_title", "Current Assignment Records")}
            page={assignmentPage}
            totalItems={assignmentCount}
            totalPages={Math.max(1, Math.ceil(assignmentCount / PAGE_SIZE))}
            pageSize={PAGE_SIZE}
            disabled={loading}
            onPageLoad={async (page) => setAssignmentPage(page)}
          />
        </div>

        <div className={cn("settings-wrapper").toClassName()}>
          <h3>
            {t("assignment_settings.audit_title", "Audit Logs")} ({auditCount})
          </h3>
          <div className={cn("assignment-settings").elem("table_actions").toClassName()}>
            <Button look="outlined" onClick={() => exportCsv("assignment-audit")} disabled={!project?.id || loading}>
              {t("assignment_settings.export_csv", "Export CSV")}
            </Button>
          </div>
          <table className={cn("assignment-settings").elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("assignment_settings.task_col", "Task")}</th>
                <th>{t("assignment_settings.action_col", "Action")}</th>
                <th>{t("assignment_settings.from_col", "From")}</th>
                <th>{t("assignment_settings.to_col", "To")}</th>
                <th>{t("assignment_settings.by_col", "By")}</th>
                <th>{t("assignment_settings.time_col", "Time")}</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((item) => (
                <tr key={item.id}>
                  <td>#{item.task_id}</td>
                  <td>{actionDisplay(item.action)}</td>
                  <td>{item?.previous_assignee?.display_name ?? "-"}</td>
                  <td>{item?.assignee?.display_name ?? "-"}</td>
                  <td>{item?.assigned_by?.display_name ?? "-"}</td>
                  <td>{item?.created_at ? new Date(item.created_at).toLocaleString() : "-"}</td>
                </tr>
              ))}
              {auditLogs.length === 0 && (
                <tr>
                  <td colSpan={6}>{t("assignment_settings.empty", "No records")}</td>
                </tr>
              )}
            </tbody>
          </table>
          <Pagination
            name="project-assignment-audit"
            label={t("assignment_settings.audit_title", "Audit Logs")}
            page={auditPage}
            totalItems={auditCount}
            totalPages={Math.max(1, Math.ceil(auditCount / PAGE_SIZE))}
            pageSize={PAGE_SIZE}
            disabled={loading}
            onPageLoad={async (page) => setAuditPage(page)}
          />
        </div>
      </div>
    </div>
  );
};

AssignmentSettings.menuItem = "assignment_settings.menu_title";
AssignmentSettings.path = "/assignment";
AssignmentSettings.title = i18next.t("assignment_settings.menu_title");
