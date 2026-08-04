import { Button, cnm } from "@humansignal/ui";
import { useTranslation } from "react-i18next";

interface FormFooterProps {
  currentStep: number;
  totalSteps: number;
  onPrevious: () => void;
  onNext: () => void;
  onSave?: () => void;
  isEditMode: boolean;
  connectionChecked: boolean;
  filesPreview: any[] | null;
  testConnection: {
    isLoading: boolean;
    mutate: () => void;
  };
  loadPreview: {
    isLoading: boolean;
    mutate: () => void;
  };
  createStorage: {
    isLoading: boolean;
  };
  saveStorage?: {
    isLoading: boolean;
  };
  target?: "import" | "export";
  isProviderDisabled?: boolean;
}

export const FormFooter = ({
  currentStep,
  totalSteps,
  onPrevious,
  onNext,
  onSave,
  isEditMode,
  connectionChecked,
  filesPreview,
  testConnection,
  loadPreview,
  createStorage,
  saveStorage,
  target,
  isProviderDisabled = false,
}: FormFooterProps) => {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between p-wide border-t border-neutral-border bg-neutral-background">
      <Button look="outlined" onClick={onPrevious} disabled={currentStep === 0}>
        {t("storage_settings.footer.previous", "Previous")}
      </Button>

      <div className="flex gap-tight items-center">
        {(isEditMode ? currentStep === 0 : currentStep === 1) && (
          <>
            <Button
              waiting={testConnection.isLoading}
              onClick={testConnection.mutate}
              variant={connectionChecked ? "positive" : "primary"}
              className={cnm({
                "border-none shadow-none bg-positive-surface-content-subtle text-positive-content pointer-events-none":
                  connectionChecked,
              })}
              style={connectionChecked ? { textShadow: "none" } : {}}
            >
              {connectionChecked
                ? t("storage_settings.footer.connection_verified", "Connection Verified")
                : t("storage_settings.footer.test_connection", "Test Connection")}
            </Button>
          </>
        )}

        {(isEditMode ? currentStep === 1 : currentStep === 2) && (
          <Button waiting={loadPreview.isLoading} onClick={loadPreview.mutate} disabled={filesPreview !== null}>
            {filesPreview !== null
              ? t("storage_settings.footer.preview_loaded", "✓ Preview Loaded")
              : t("storage_settings.footer.load_preview", "Load Preview")}
          </Button>
        )}

        <Button
          onClick={onNext}
          waiting={currentStep === totalSteps - 1 && createStorage.isLoading}
          disabled={
            (!isEditMode && currentStep === 1 && !connectionChecked) || (currentStep === 0 && isProviderDisabled)
          }
          look={currentStep === totalSteps - 1 && target !== "export" ? "outlined" : undefined}
          tooltip={
            currentStep === 1 && !connectionChecked
              ? t("storage_settings.footer.tooltips.test_before_continue", "Test connection before continuing")
              : currentStep === 0 && isProviderDisabled
                ? t(
                    "storage_settings.footer.tooltips.provider_disabled",
                    "This provider is not available in the current version",
                  )
                : undefined
          }
        >
          {currentStep < totalSteps - 1
            ? t("storage_settings.footer.next", "Next")
            : target === "export"
              ? t("storage_settings.footer.save", "Save")
              : t("storage_settings.footer.save_sync", "Save & Sync")}
        </Button>

        {currentStep === totalSteps - 1 && target !== "export" && onSave && (
          <Button onClick={onSave} waiting={saveStorage?.isLoading}>
            {t("storage_settings.footer.save", "Save")}
          </Button>
        )}
      </div>
    </div>
  );
};
