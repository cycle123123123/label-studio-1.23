import { inject, observer } from "mobx-react";
import { useTranslation } from "react-i18next";
import { RadioGroup } from "../../Common/RadioGroup/RadioGroup";
import { IconGrid, IconList } from "@humansignal/icons";
import { Tooltip } from "@humansignal/ui";

const viewInjector = inject(({ store }) => ({
  view: store.currentView,
}));

export const ViewToggle = viewInjector(
  observer(({ view, size, ...rest }) => {
    const { t } = useTranslation();

    return (
      <RadioGroup
        size={size}
        value={view.type}
        onChange={(e) => view.setType(e.target.value)}
        {...rest}
        style={{ "--button-padding": "0 var(--spacing-tighter)" }}
      >
        <Tooltip title={t("data_manager.list_view", "List view")}>
          <div>
            <RadioGroup.Button value="list" aria-label={t("data_manager.list_view", "Switch to list view")}>
              <IconList />
            </RadioGroup.Button>
          </div>
        </Tooltip>
        <Tooltip title={t("data_manager.grid_view", "Grid view")}>
          <div>
            <RadioGroup.Button value="grid" aria-label={t("data_manager.grid_view", "Switch to grid view")}>
              <IconGrid />
            </RadioGroup.Button>
          </div>
        </Tooltip>
      </RadioGroup>
    );
  }),
);

export const DataStoreToggle = viewInjector(({ view, size, ...rest }) => {
  const { t } = useTranslation();

  return (
    <RadioGroup value={view.target} size={size} onChange={(e) => view.setTarget(e.target.value)} {...rest}>
      <RadioGroup.Button value="tasks">{t("data_manager.tasks", "Tasks")}</RadioGroup.Button>
      <RadioGroup.Button value="annotations" disabled>
        {t("data_manager.annotations", "Annotations")}
      </RadioGroup.Button>
    </RadioGroup>
  );
});
