import { useCopyText } from "@humansignal/core";
import { IconEllipsis, IconLink } from "@humansignal/icons";
import { Button, ToastType, useToast } from "@humansignal/ui";
import { observer } from "mobx-react";
import { type FC, useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../../../utils/bem";
import { ContextMenu, type ContextMenuAction, ContextMenuTrigger, type MenuActionOnClick } from "../../ContextMenu";

export const RegionContextMenu: FC<{ item: any }> = observer(({ item }: { item: any }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const regionLink = useMemo(() => {
    const url = new URL(window.location.href);
    if (item.annotation.pk) {
      url.searchParams.set("annotation", item.annotation.pk);
    }
    if (item.id) {
      url.searchParams.set("region", item.id.split("#")[0]);
    }
    return url.toString();
  }, [item]);
  const [copyLink] = useCopyText({ defaultText: regionLink });
  const toast = useToast();

  const onCopyLink = useCallback<MenuActionOnClick>(
    (_, ctx) => {
      copyLink();
      ctx.dropdown?.close();
      toast.show({
        message: t("region.link_copied", "Region link copied to clipboard"),
        type: ToastType.info,
      });
    },
    [copyLink],
  );

  const actions = useMemo<ContextMenuAction[]>(
    () => [
      {
        label: t("region.copy_link", "Copy Region Link"),
        onClick: onCopyLink,
        icon: <IconLink />,
      },
    ],
    [onCopyLink],
  );

  return (
    <ContextMenuTrigger
      className={cn("region-context-menu").mod({ open }).toClassName()}
      content={<ContextMenu actions={actions} />}
      onToggle={(isOpen) => setOpen(isOpen)}
    >
      <Button variant="neutral" look="string" size="smaller" aria-label={t("region.options", "Region options")}>
        <IconEllipsis />
      </Button>
    </ContextMenuTrigger>
  );
});
