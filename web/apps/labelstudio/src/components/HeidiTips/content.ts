import i18next from "i18next";
import type { TipsCollection } from "./types";

export const defaultTipsCollection: TipsCollection = {
  projectCreation: [
    {
      title: i18next.t("heidi_tips.find_and_manage_projects.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.find_and_manage_projects.content",
        "It’s easier to find the projects when you organize them into workspaces using Label Studio Enterprise.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.find_and_manage_projects.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/manage_projects#Create-workspaces-to-organize-projects",
        params: {
          experiment: "project_creation_tip",
          treatment: "find_and_manage_projects",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.faster_provisioning.title", "Unlock faster access provisioning"),
      content: i18next.t(
        "heidi_tips.faster_provisioning.content",
        "Streamline assigning staff to multiple projects by assigning them to workspaces in Label Studio Enterprise.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.faster_provisioning.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/manage_projects#Add-or-remove-members-to-a-workspace",
        params: {
          experiment: "project_creation_tip",
          treatment: "faster_provisioning",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.annotator_dashboard.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.annotator_dashboard.content",
        "In the Enterprise platform, admins can view annotator performance dashboards to optimize resource allocation, improve team management, and inform compensation.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.annotator_dashboard.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/dashboard_annotator",
        params: {
          experiment: "project_creation_tip",
          treatment: "annotator_dashboard",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.access_to_projects.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.access_to_projects.content",
        "You can control access to specific projects and workspaces for internal team members and external annotators using Label Studio Enterprise.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.access_to_projects.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/manage_users#Roles-in-Label-Studio-Enterprise",
        params: {
          experiment: "project_creation_tip",
          treatment: "access_to_projects",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.templates.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.templates.content",
        "You can use or modify dozens or templates to configure your labeling UI, or create a custom configuration from scratch using simple XML-like tag.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.templates.link_label", "Learn more"),
        url: "https://labelstud.io/guide/setup",
        params: {
          experiment: "project_creation_tip",
          treatment: "templates",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.genai_templates.title", "Labeling for GenAI"),
      content: i18next.t(
        "heidi_tips.genai_templates.content",
        "Label Studio has templates available for supervised LLM fine-tuning, RAG retrieval ranking, RLHF, chatbot evaluation, and more.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.genai_templates.link_label", "Explore templates"),
        url: "https://labelstud.io/templates/gallery_generative_ai",
        params: {
          experiment: "project_creation_tip",
          treatment: "genai_templates",
        },
      },
    },
  ],
  organizationPage: [
    {
      title: i18next.t("heidi_tips.team_growing.title", "It looks like your team is growing!"),
      content: i18next.t(
        "heidi_tips.team_growing.content",
        "Assign roles to your team using Label Studio Enterprise and control access to sensitive data at the project and workspace levels.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.team_growing.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/manage_users#Roles-in-Label-Studio-Enterprise",
        params: {
          experiment: "organization_page_tip",
          treatment: "team_growing",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.enable_sso.title", "Want to simplify and secure logging in?"),
      content: i18next.t(
        "heidi_tips.enable_sso.content",
        "Enable Single Sign-On for your team using SAML, SCIM2 or LDAP with Label Studio Enterprise.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.enable_sso.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/auth_setup",
        params: {
          experiment: "organization_page_tip",
          treatment: "enable_sso",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.starter_cloud_live.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.starter_cloud_live.content",
        "Try Label Studio Starter Cloud, optimized for small teams and projects.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.starter_cloud_live.link_label", "Learn more"),
        url: "https://humansignal.com/pricing/",
        params: {
          experiment: "organization_page_tip",
          treatment: "starter_cloud_live",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.automate_distribution.title", "Want to automate task distribution?"),
      content: i18next.t(
        "heidi_tips.automate_distribution.content",
        "Create rules, automate how tasks are distributed to annotators, and only show tasks assigned to each annotator in their view.and control task visibility for each annotator.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.automate_distribution.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/setup_project#Set-up-annotation-settings-for-your-project",
        params: {
          experiment: "organization_page_tip",
          treatment: "automate_distribution",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.share_knowledge.title", "Share knowledge with the community"),
      content: i18next.t(
        "heidi_tips.share_knowledge.content",
        "Have questions or a tip to share with other Label Studio users? Join the community slack channel for the latest updates. ",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.share_knowledge.link_label", "Join the community"),
        url: "https://label-studio.slack.com",
        params: {
          experiment: "organization_page_tip",
          treatment: "share_knowledge",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.integration_points.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.integration_points.content",
        "Label Studio supports multiple points of integration with cloud storage, machine learning models, and popular tools to automate your machine learning pipeline.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.integration_points.link_label", "Check out the integrations directory"),
        url: "https://labelstud.io/integrations/",
        params: {
          experiment: "organization_page_tip",
          treatment: "integration_points",
        },
      },
    },
  ],
  projectSettings: [
    {
      title: i18next.t("heidi_tips.aws_marketplace.title", "Apply your AWS spend to Label Studio Enterprise"),
      content: i18next.t(
        "heidi_tips.aws_marketplace.content",
        "Label Studio Enterprise is now available on the AWS Marketplace so you can use your committed spend to streamline data labeling workflows.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.aws_marketplace.link_label", "Learn more"),
        url: "https://aws.amazon.com/marketplace/pp/prodview-wjac3msf77tny",
        params: {
          experiment: "project_settings_tip",
          treatment: "aws_marketplace",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.auto_labeling.title", "Save time with Auto-Labeling"),
      content: i18next.t(
        "heidi_tips.auto_labeling.content",
        "Use automation to instantly label large-scale datasets without sacrificing quality in the Enterprise platform.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.auto_labeling.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/prompts_overview#Auto-labeling-with-Prompts",
        params: {
          experiment: "project_settings_tip",
          treatment: "auto_labeling",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.quality_and_agreement.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.quality_and_agreement.content",
        "You can increase the quality of your labeled data with reviewer workflows and task agreement scores using Label Studio Enterprise.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.quality_and_agreement.link_label", "Learn more"),
        url: "https://docs.humansignal.com/guide/quality",
        params: {
          experiment: "project_settings_tip",
          treatment: "quality_and_agreement",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.evals.title", "Evaluate GenAI models"),
      content: i18next.t(
        "heidi_tips.evals.content",
        "Combine automation plus human supervision to evaluate and ensure LLM quality in the Enterprise platform.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.evals.link_label", "Learn more"),
        url: "https://humansignal.com/evals/",
        params: {
          experiment: "project_settings_tip",
          treatment: "evals",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.infrastructure_and_upgrades.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.infrastructure_and_upgrades.content",
        "You can save time managing infrastructure and upgrades, plus access more features for automation, quality, and team management, by using the Enterprise cloud service.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.infrastructure_and_upgrades.link_label", "Learn more"),
        url: "https://humansignal.com/platform/",
        params: {
          experiment: "project_settings_tip",
          treatment: "infrastructure_and_upgrades",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.starter_cloud_live_b.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.starter_cloud_live_b.content",
        "Try Label Studio Starter Cloud, optimized for small teams and projects.",
      ),
      link: {
        label: i18next.t("heidi_tips.starter_cloud_live_b.link_label", "Learn more"),
        url: "https://humansignal.com/pricing/",
        params: {
          experiment: "project_settings_tip",
          treatment: "starter_cloud_live",
        },
      },
    },
    {
      title: i18next.t("heidi_tips.connect_ml_models.title", "Did you know?"),
      content: i18next.t(
        "heidi_tips.connect_ml_models.content",
        "You can connect ML models using the backend SDK to save time with pre-labeling or active learning.",
      ),
      closable: true,
      link: {
        label: i18next.t("heidi_tips.connect_ml_models.link_label", "Learn more"),
        url: "https://labelstud.io/guide/ml",
        params: {
          experiment: "project_settings_tip",
          treatment: "connect_ml_models",
        },
      },
    },
  ],
};
