import i18next from "i18next";
const t = i18next.t;
import { z } from "zod";
import type { ProviderConfig } from "@humansignal/app-common/blocks/StorageProviderForm/types/provider";
import { IconCloudProviderRedis } from "@humansignal/icons";

export const redisProvider: ProviderConfig = {
  name: "redis",
  title: t("storage_settings.providers.redis.title"),
  description: t("storage_settings.providers.redis.description"),
  icon: IconCloudProviderRedis,
  fields: [
    {
      name: "db",
      type: "text",
      label: t("storage_settings.providers.redis.fields.db.label"),
      placeholder: "1",
      schema: z.string().default("1"),
    },
    {
      name: "password",
      type: "password",
      label: t("storage_settings.providers.redis.fields.password.label"),
      autoComplete: "new-password",
      placeholder: t("storage_settings.providers.redis.fields.password.placeholder"),
      schema: z.string().optional().default(""),
    },
    {
      name: "host",
      type: "text",
      label: t("storage_settings.providers.redis.fields.host.label"),
      required: true,
      placeholder: t("storage_settings.providers.redis.fields.host.placeholder"),
      schema: z.string().min(1, "Host is required"),
    },
    {
      name: "port",
      type: "text",
      label: t("storage_settings.providers.redis.fields.port.label"),
      placeholder: "6379",
      schema: z.string().default("6379"),
    },
    {
      name: "prefix",
      type: "text",
      label: t("storage_settings.providers.redis.fields.prefix.label"),
      placeholder: t("storage_settings.providers.redis.fields.prefix.placeholder"),
      schema: z.string().optional().default(""),
      target: "export",
    },
  ],
  layout: [{ fields: ["host", "port", "db", "password"] }, { fields: ["prefix"] }],
};

export default redisProvider;
