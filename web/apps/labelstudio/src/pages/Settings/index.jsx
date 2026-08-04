import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import i18next from "i18next";
import { useProject } from "../../providers/ProjectProvider";
import { WebhookPage } from "../WebhookPage/WebhookPage";
import { DangerZone } from "./DangerZone";
import { GeneralSettings } from "./GeneralSettings";
import { AnnotationSettings } from "./AnnotationSettings";
import { LabelingSettings } from "./LabelingSettings";
import { AssignmentSettings } from "./AssignmentSettings";
import { WorkflowAuditSettings } from "./WorkflowAuditSettings";
import { StatisticsSettings } from "./StatisticsSettings";
import { MachineLearningSettings } from "./MachineLearningSettings/MachineLearningSettings";
import { PredictionsSettings } from "./PredictionsSettings/PredictionsSettings";
import { StorageSettings } from "./StorageSettings/StorageSettings";
import "./settings.scss";

export const MenuLayout = ({ children, ...routeProps }) => {
  const { project } = useProject();
  const canManageAssignments = Boolean(project?.assignment_settings?.can_manage);

  return (
    <SidebarMenu
      menuItems={[
        GeneralSettings,
        LabelingSettings,
        canManageAssignments && AssignmentSettings,
        canManageAssignments && WorkflowAuditSettings,
        canManageAssignments && StatisticsSettings,
        AnnotationSettings,
        MachineLearningSettings,
        PredictionsSettings,
        StorageSettings,
        WebhookPage,
        DangerZone,
      ].filter(Boolean)}
      path={routeProps.match.url}
      children={children}
    />
  );
};

const pages = {
  AnnotationSettings,
  LabelingSettings,
  AssignmentSettings,
  WorkflowAuditSettings,
  StatisticsSettings,
  MachineLearningSettings,
  PredictionsSettings,
  StorageSettings,
  WebhookPage,
  DangerZone,
};

export const SettingsPage = {
  title: i18next.t("settings_page_title", "Settings"),
  path: "/settings",
  exact: true,
  layout: MenuLayout,
  component: GeneralSettings,
  pages,
};
