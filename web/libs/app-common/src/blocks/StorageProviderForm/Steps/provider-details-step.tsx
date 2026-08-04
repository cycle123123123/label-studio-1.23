import { getProviderConfig } from "../providers";
import { ProviderForm } from "../components/provider-form";
import Input from "apps/labelstudio/src/components/Form/Elements/Input/Input";
import { Toggle } from "@humansignal/ui";
import { useTranslation } from "react-i18next";

interface ProviderDetailsStepProps {
  formData: any;
  errors: Record<string, string>;
  handleProviderFieldChange: (name: string, value: any) => void;
  handleFieldBlur?: (name: string, value: any) => void;
  provider?: string;
  isEditMode?: boolean;
  target?: "import" | "export";
}

export const ProviderDetailsStep = ({
  formData,
  errors,
  handleProviderFieldChange,
  handleFieldBlur,
  provider,
  isEditMode = false,
  target,
}: ProviderDetailsStepProps) => {
  const { t } = useTranslation();
  const providerConfig = getProviderConfig(provider);

  if (!provider || !providerConfig) {
    return (
      <div className="text-red-500">
        {!provider
          ? t("storage_settings.details_step.error_no_provider", "No provider selected")
          : t("storage_settings.details_step.error_unknown_provider", {
              provider,
              defaultValue: "Unknown provider: {{provider}}",
            })}
      </div>
    );
  }

  const providerTitle = t(`storage_settings.providers.${provider}.title`, providerConfig.title);
  const providerDescription = t(`storage_settings.providers.${provider}.description`, providerConfig.description);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{providerTitle}</h2>
        <p className="text-muted-foreground">{providerDescription}</p>
      </div>

      {/* Title field - common for all providers */}
      <div className="space-y-2">
        <Input
          name="title"
          value={formData.title ?? ""}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleProviderFieldChange("title", e.target.value)}
          placeholder={t(
            "storage_settings.details_step.title.placeholder",
            "Enter a descriptive name (e.g., 'Legal Documents', 'Training Data')",
          )}
          validate=""
          skip={false}
          labelProps={{}}
          ghost={false}
          tooltip=""
          tooltipIcon={null}
          required={true}
          label={t("storage_settings.details_step.title.label", "Storage Title")}
          description={t(
            "storage_settings.details_step.title.description",
            "This name will help you identify this connection in your project",
          )}
          footer={errors.title ? <span className="text-negative-content">{errors.title}</span> : ""}
          className={errors.title ? "border-negative-content" : ""}
        />
      </div>

      <ProviderForm
        provider={providerConfig}
        formData={formData}
        errors={errors}
        onChange={handleProviderFieldChange}
        onBlur={handleFieldBlur}
        isEditMode={isEditMode}
        target={target}
      />

      {/* Export-specific common fields */}
      {target === "export" && (
        <div className="space-y-6">
          <div className="space-y-2">
            <Toggle
              checked={formData.can_delete_objects ?? false}
              onChange={(e) => handleProviderFieldChange("can_delete_objects", e.target.checked)}
              aria-label={t("storage_settings.details_step.can_delete_objects.label", "Can delete objects from storage")}
              label={t("storage_settings.details_step.can_delete_objects.label", "Can delete objects from storage")}
              description={t(
                "storage_settings.details_step.can_delete_objects.description",
                "If unchecked, annotations will not be deleted from storage",
              )}
            />
          </div>
        </div>
      )}
    </div>
  );
};
