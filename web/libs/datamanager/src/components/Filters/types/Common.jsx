import { FilterDropdown } from "../FilterDropdown";
import i18next from "i18next";

export const Common = [
  {
    key: "empty",
    label: "is empty",
    input: (props) => (
      <FilterDropdown
        value={props.value ?? false}
        onChange={(value) => props.onChange(value)}
        items={[
          { value: true, label: i18next.t("filters.yes", "yes") },
          { value: false, label: i18next.t("filters.no", "no") },
        ]}
        disabled={props.disabled}
      />
    ),
  },
];
