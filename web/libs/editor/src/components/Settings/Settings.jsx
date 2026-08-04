import React, { useMemo } from "react";
import { Modal, Table, Tabs } from "antd";
import { observer } from "mobx-react";
import { useTranslation } from "react-i18next";

import { Hotkey } from "../../core/Hotkey";

import "./Settings.scss";
import { cn } from "../../utils/bem";
import { triggerResizeEvent } from "../../utils/utilities";

import EditorSettings from "../../core/settings/editorsettings";
import * as TagSettings from "./TagSettings";
import { IconClose } from "@humansignal/icons";
import { Checkbox, Toggle } from "@humansignal/ui";
import { ff } from "@humansignal/core";

const HotkeysDescription = () => {
  const { t } = useTranslation();
  const columns = [
    { title: t("hotkeys.shortcut", "Shortcut"), dataIndex: "combo", key: "combo" },
    { title: t("hotkeys.description", "Description"), dataIndex: "descr", key: "descr" },
  ];

  const keyNamespaces = Hotkey.namespaces();

  const getData = (descr) =>
    Object.keys(descr)
      .filter((k) => descr[k])
      .map((k) => ({
        key: k,
        combo: k.split(",").map((keyGroup) => {
          return (
            <div className={cn("keys").elem("key-group").toClassName()} key={keyGroup}>
              {keyGroup
                .trim()
                .split("+")
                .map((k) => (
                  <kbd className={cn("keys").elem("key").toClassName()} key={k}>
                    {k}
                  </kbd>
                ))}
            </div>
          );
        }),
        descr: t(`hotkeys.${descr[k]}`, descr[k]),
      }));

  return (
    <div className={cn("keys").toClassName()}>
      <Tabs size="small">
        {Object.entries(keyNamespaces).map(([ns, data]) => {
          if (Object.keys(data.descriptions).length === 0) {
            return null;
          }
          return (
            <Tabs.TabPane key={ns} tab={t(`hotkeys.${ns}`, data.description ?? ns)}>
              <Table columns={columns} dataSource={getData(data.descriptions)} size="small" />
            </Tabs.TabPane>
          );
        })}
      </Tabs>
    </div>
  );
};

const newUI = { newUI: true };

const editorSettingsKeys = Object.keys(EditorSettings).filter((key) => {
  const flag = EditorSettings[key].flag;
  return flag ? ff.isActive(flag) : true;
});

const enableTooltipsIndex = editorSettingsKeys.findIndex((key) => key === "enableTooltips");
const enableLabelTooltipsIndex = editorSettingsKeys.findIndex((key) => key === "enableLabelTooltips");

// swap these in the array (new UI order)
const tmp = editorSettingsKeys[enableTooltipsIndex];

editorSettingsKeys[enableTooltipsIndex] = editorSettingsKeys[enableLabelTooltipsIndex];
editorSettingsKeys[enableLabelTooltipsIndex] = tmp;

const SettingsTag = ({ children }) => {
  return <div className={cn("settings-tag").toClassName()}>{children}</div>;
};

const GeneralSettings = observer(({ store }) => {
  const { t } = useTranslation();
  return (
    <div className={cn("settings").mod(newUI).toClassName()}>
      {editorSettingsKeys.map((obj, index) => {
        return (
          <label className={cn("settings").elem("field").toClassName()} key={index}>
            <>
              <div className={cn("settings__label").toClassName()}>
                <div className={cn("settings__label").elem("title").toClassName()}>
                  {t(`settings_modal.general.${obj}.title`, EditorSettings[obj].newUI.title)}
                  {EditorSettings[obj].newUI.tags?.split(",").map((tag) => (
                    <SettingsTag key={tag}>{t(`settings_modal.general.${obj}.tags`, tag)}</SettingsTag>
                  ))}
                </div>
                <div className={cn("settings__label").elem("description").toClassName()}>
                  {t(`settings_modal.general.${obj}.description`, EditorSettings[obj].newUI.description)}
                </div>
              </div>
              <Toggle
                key={index}
                checked={store.settings[obj]}
                onChange={store.settings[EditorSettings[obj].onChangeEvent]}
                description={t(`settings_modal.general.${obj}.toggle_description`, EditorSettings[obj].description)}
              />
            </>
          </label>
        );
      })}
    </div>
  );
});

const LayoutSettings = observer(({ store }) => {
  const { t } = useTranslation();
  return (
    <div className={cn("settings").mod(newUI).toClassName()}>
      <div className={cn("settings").elem("field").toClassName()}>
        <Checkbox
          checked={store.settings.bottomSidePanel}
          onChange={() => {
            store.settings.toggleBottomSP();
            setTimeout(triggerResizeEvent);
          }}
        >
          {t("settings_modal.layout.move_bottom", "Move sidepanel to the bottom")}
        </Checkbox>
      </div>

      <div className={cn("settings").elem("field").toClassName()}>
        <Checkbox checked={store.settings.displayLabelsByDefault} onChange={store.settings.toggleSidepanelModel}>
          {t("settings_modal.layout.display_labels", "Display Labels by default in Results panel")}
        </Checkbox>
      </div>

      <div className={cn("settings").elem("field").toClassName()}>
        <Checkbox
          value="Show Annotations panel"
          defaultChecked={store.settings.showAnnotationsPanel}
          onChange={() => {
            store.settings.toggleAnnotationsPanel();
          }}
        >
          {t("settings_modal.layout.show_annotations", "Show Annotations panel")}
        </Checkbox>
      </div>

      <div className={cn("settings").elem("field").toClassName()}>
        <Checkbox
          value="Show Predictions panel"
          defaultChecked={store.settings.showPredictionsPanel}
          onChange={() => {
            store.settings.togglePredictionsPanel();
          }}
        >
          {t("settings_modal.layout.show_predictions", "Show Predictions panel")}
        </Checkbox>
      </div>

      {/* Saved for future use */}
      {/* <div className={cn("settings").elem("field").toClassName()}>
        <Checkbox
          value="Show image in fullsize"
          defaultChecked={store.settings.imageFullSize}
          onChange={() => {
            store.settings.toggleImageFS();
          }}
        >
          Show image in fullsize
        </Checkbox>
      </div> */}
    </div>
  );
});

const Settings = {
  General: { name: "General", component: GeneralSettings },
  Hotkeys: { name: "Hotkeys", component: HotkeysDescription },
};

const DEFAULT_ACTIVE = Object.keys(Settings)[0];

const DEFAULT_MODAL_SETTINGS = {
  name: "settings-modal",
  closeIcon: <IconClose />,
};

export default observer(({ store }) => {
  const { t } = useTranslation();
  const modalSettings = {
    ...DEFAULT_MODAL_SETTINGS,
    title: t("settings_modal.title_new_ui", "Labeling Interface Settings"),
  };
  const availableSettings = useMemo(() => {
    const availableTags = Object.values(store.annotationStore.names.toJSON());
    const settingsScreens = Object.values(TagSettings);

    return availableTags.reduce((res, tagName) => {
      const tagType = store.annotationStore.names.get(tagName).type;
      const settings = settingsScreens.find(({ tagName }) => tagName.toLowerCase() === tagType.toLowerCase());

      if (settings) res.push(settings);

      return res;
    }, []);
  }, []);

  return (
    <Modal
      className={cn(modalSettings.name).toClassName()}
      open={store.showingSettings}
      onCancel={store.toggleSettings}
      footer=""
      title={modalSettings.title}
      closeIcon={modalSettings.closeIcon}
      bodyStyle={modalSettings.bodyStyle}
    >
      <Tabs defaultActiveKey={DEFAULT_ACTIVE}>
        {Object.entries(Settings).map(([key, { name, component }]) => (
          <Tabs.TabPane tab={t(`settings_modal.tabs.${key.toLowerCase()}`, name)} key={key}>
            {React.createElement(component, { store })}
          </Tabs.TabPane>
        ))}
        {availableSettings.map((Page) => (
          <Tabs.TabPane tab={t(`settings_modal.tag.${Page.tagName}.title`, Page.title)} key={Page.tagName}>
            <Page store={store} />
          </Tabs.TabPane>
        ))}
      </Tabs>
    </Modal>
  );
});
