import i18next from "i18next";
const t = i18next.t;
import type { ProviderConfig } from "@humansignal/app-common/blocks/StorageProviderForm/types/provider";
import { IconCloudProviderAzure } from "@humansignal/icons";
import { z } from "zod";

export const azureProvider: ProviderConfig = {
  name: "azure",
  title: t("storage_settings.providers.azure.title"),
  description: t("storage_settings.providers.azure.description"),
  icon: IconCloudProviderAzure,
  fields: [
    {
      name: "container",
      type: "text",
      label: t("storage_settings.providers.azure.fields.container.label"),
      required: true,
      placeholder: t("storage_settings.providers.azure.fields.container.placeholder"),
      schema: z.string().min(1, "Container name is required"),
    },
    {
      name: "prefix",
      type: "text",
      label: t("storage_settings.providers.azure.fields.prefix.label"),
      placeholder: t("storage_settings.providers.azure.fields.prefix.placeholder"),
      schema: z.string().optional().default(""),
      target: "export",
    },
    {
      name: "account_name",
      type: "password",
      label: t("storage_settings.providers.azure.fields.account_name.label"),
      autoComplete: "off",
      accessKey: true,
      placeholder: t("storage_settings.providers.azure.fields.account_name.placeholder"),
      schema: z.string().optional().default(""),
    },
    {
      name: "account_key",
      type: "password",
      label: t("storage_settings.providers.azure.fields.account_key.label"),
      autoComplete: "new-password",
      accessKey: true,
      placeholder: t("storage_settings.providers.azure.fields.account_key.placeholder"),
      schema: z.string().optional().default(""),
    },
    {
      name: "presign",
      type: "toggle",
      label: t("storage_settings.providers.azure.fields.presign.label"),
      description:
        "When pre-signed URLs are enabled, all data bypasses the platform and user browsers directly read data from storage",
      schema: z.boolean().default(true),
      target: "import",
      resetConnection: false,
    },
    {
      name: "presign_ttl",
      type: "counter",
      label: t("storage_settings.providers.azure.fields.presign_ttl.label"),
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
    { fields: ["container"] },
    { fields: ["prefix"] },
    { fields: ["account_name"] },
    { fields: ["account_key"] },
    { fields: ["presign", "presign_ttl"] },
  ],
};

export default azureProvider;
