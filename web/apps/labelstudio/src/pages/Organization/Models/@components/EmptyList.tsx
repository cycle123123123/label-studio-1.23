import { Button } from "@humansignal/ui";
import { cn } from "apps/labelstudio/src/utils/bem";
import type { FC } from "react";
import { useTranslation } from "react-i18next";
import "./EmptyList.scss";
import { HeidiAi } from "apps/labelstudio/src/assets/images";

export const EmptyList: FC = () => {
  const { t } = useTranslation();
  return (
    <div className={cn("empty-models-list").toClassName()}>
      <div className={cn("empty-models-list").elem("content").toClassName()}>
        <div className={cn("empty-models-list").elem("heidy").toClassName()}>
          <HeidiAi />
        </div>
        <div className={cn("empty-models-list").elem("title").toClassName()}>
          {t("models.create_model", "Create a Model")}
        </div>
        <div className={cn("empty-models-list").elem("caption").toClassName()}>
          {t("models.empty_desc", "Build a high quality model to auto-label your data using LLMs")}
        </div>
        <Button aria-label={t("models.create_new_model_aria", "Create new model")}>
          {t("models.create_model", "Create a Model")}
        </Button>
      </div>
    </div>
  );
};
