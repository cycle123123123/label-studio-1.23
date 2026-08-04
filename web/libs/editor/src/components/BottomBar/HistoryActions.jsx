import { observer } from "mobx-react";
import { IconRedo, IconReset, IconUndo } from "@humansignal/icons";
import { Tooltip, Button } from "@humansignal/ui";
import { useTranslation } from "react-i18next";
import { cn } from "../../utils/bem";
import "./HistoryActions.scss";

export const EditingHistory = observer(({ entity }) => {
  const { t } = useTranslation();
  const { history } = entity;

  return (
    <div className={cn("history-buttons").toClassName()}>
      <Tooltip title={t("lsf.history_actions.undo", "Undo")}>
        <Button
          variant="neutral"
          size="small"
          aria-label={t("lsf.history_actions.undo", "Undo")}
          look="string"
          disabled={!history?.canUndo}
          onClick={() => entity.undo()}
          className="aspect-square"
          leading={<IconUndo />}
          data-testid="bottombar-undo-button"
        />
      </Tooltip>
      <Tooltip title={t("lsf.history_actions.redo", "Redo")}>
        <Button
          variant="neutral"
          size="small"
          look="string"
          aria-label={t("lsf.history_actions.redo", "Redo")}
          disabled={!history?.canRedo}
          onClick={() => entity.redo()}
          className="aspect-square"
          leading={<IconRedo />}
          data-testid="bottombar-redo-button"
        />
      </Tooltip>
      <Tooltip title={t("lsf.history_actions.reset", "Reset")}>
        <Button
          variant="negative"
          look="string"
          size="small"
          aria-label={t("lsf.history_actions.reset", "Reset")}
          disabled={!history?.canUndo}
          onClick={() => history?.reset()}
          className="aspect-square"
          leading={<IconReset />}
          data-testid="bottombar-reset-button"
        />
      </Tooltip>
    </div>
  );
});
