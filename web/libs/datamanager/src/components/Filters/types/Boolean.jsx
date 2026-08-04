import { FilterDropdown } from "../FilterDropdown";
import i18next from "i18next";

export const BooleanFilter = [
  {
    key: "equal",
    label: "is",
    valueType: "single",
    input: (props) => (
      <FilterDropdown
        defaultValue={props.value ?? false}
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
