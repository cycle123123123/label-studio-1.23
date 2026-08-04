import i18next from "i18next";
const t = i18next.t;
import { z } from "zod";
import type { ProviderConfig } from "@humansignal/app-common/blocks/StorageProviderForm/types/provider";
import { IconCloudProviderGCS } from "@humansignal/icons";

export const gcsProvider: ProviderConfig = {
  name: "gcs",
  title: t("storage_settings.providers.gcs.title"),
  description: t("storage_settings.providers.gcs.description"),
  icon: IconCloudProviderGCS,
  fields: [
    {
      name: "bucket",
      type: "text",
      label: t("storage_settings.providers.gcs.fields.bucket.label"),
      required: true,
      schema: z.string().min(1, "Bucket name is required"),
    },
    {
      name: "prefix",
      type: "text",
      label: t("storage_settings.providers.gcs.fields.prefix.label"),
      placeholder: t("storage_settings.providers.gcs.fields.prefix.placeholder"),
      schema: z.string().optional().default(""),
      target: "export",
    },
    {
      name: "google_application_credentials",
      type: "password",
      label: t("storage_settings.providers.gcs.fields.google_application_credentials.label"),
      description: t("storage_settings.providers.gcs.description"),
      autoComplete: "new-password",
      accessKey: true,
      schema: z.string().optional().default(""), // JSON validation could be added if needed
    },
    {
      name: "google_project_id",
      type: "text",
      label: t("storage_settings.providers.gcs.fields.google_project_id.label"),
      description: t("storage_settings.providers.gcs.description"),
      schema: z.string().optional().default(""),
    },
    {
      name: "presign",
      type: "toggle",
      label: t("storage_settings.providers.gcs.fields.presign.label"),
      description:
        "When pre-signed URLs are enabled, all data bypasses the platform and user browsers directly read data from storage",
      schema: z.boolean().default(true),
      target: "import",
      resetConnection: false,
    },
    {
      name: "presign_ttl",
      type: "counter",
      label: t("storage_settings.providers.gcs.fields.presign_ttl.label"),
      min: 1,
      max: 10080,
      step: 1,
      schema: z.number().min(1).max(10080).default(15),
      target: "import",
      resetConnection: false,
      dependsOn: {
        field: "presign",
        value: true,
      },
    },
  ],
  layout: [
    { fields: ["bucket"] },
    { fields: ["prefix"] },
    { fields: ["google_application_credentials"] },
    { fields: ["google_project_id"] },
    { fields: ["presign", "presign_ttl"] },
  ],
};

export default gcsProvider;
