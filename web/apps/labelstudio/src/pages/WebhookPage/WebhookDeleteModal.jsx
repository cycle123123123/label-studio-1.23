import { Button } from "@humansignal/ui";
import { useTranslation } from "react-i18next";
import { modal } from "../../components/Modal/Modal";
import { useModalControls } from "../../components/Modal/ModalPopup";
import { Space } from "../../components/Space/Space";
import { cn } from "../../utils/bem";

export const WebhookDeleteModal = ({ onDelete }) => {
  const { t } = useTranslation();
  return modal({
    title: t("common.delete", "Delete"),
    body: () => {
      const ctrl = useModalControls();
      const rootClass = cn("webhook-delete-modal");
      return (
        <div className={rootClass}>
          <div className={rootClass.elem("modal-text").toClassName()}>
            {t(
              "webhook_delete_modal.confirmation_message",
              "Are you sure you want to delete this webhook? This action cannot be undone.",
            )}
          </div>
        </div>
      );
    },
    footer: () => {
      const ctrl = useModalControls();
      const rootClass = cn("webhook-delete-modal");
      return (
        <Space align="end">
          <Button
            look="outlined"
            onClick={() => {
              ctrl.hide();
            }}
            aria-label={t("webhook_delete_modal.cancel_aria", "Cancel webhook deletion")}
          >
            {t("cancel", "Cancel")}
          </Button>
          <Button
            variant="negative"
            onClick={async () => {
              await onDelete();
              ctrl.hide();
            }}
            aria-label={t("webhook_delete_modal.confirm_aria", "Confirm webhook deletion")}
          >
            {t("webhook_delete_modal.delete_button", "Delete Webhook")}
          </Button>
        </Space>
      );
    },
    style: { width: 512 },
  });
};
