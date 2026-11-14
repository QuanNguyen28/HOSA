import { useState } from "react";
import { useTranslation } from "../i18n/language";
import { CoordinateFields, actionClass } from "./backend";
import type { Site } from "./model";
import { coords } from "./ui";

export type CustomPoint = { id: string; lat: number; lon: number };
/** One tab's own site choice: Compare and Best dates never share it. */
export type SiteChoice = { selected: string[]; customs: CustomPoint[]; next: number };

/** Not offered by Compare or Best dates. */
export const PLANNING_EXCLUDED = new Set(["connecting-ridge-extension"]);

export const validCoordinate = (lat: number, lon: number) =>
  Number.isFinite(lat) && lat > -90 && lat < 90 && Number.isFinite(lon) && lon >= -180 && lon <= 360;

export function initialChoice(sites: Site[]): SiteChoice {
  return { selected: sites.slice(0, 2).map((site) => site.id), customs: [], next: 1 };
}

/** Custom points as sites, named "Custom point i" by their position in the list. */
export function customSites(customs: CustomPoint[], name: (i: number) => string): Site[] {
  return customs.map((point, i) => ({
    id: point.id,
    name: name(i + 1),
    group: "illumination",
    lat: point.lat,
    lon: point.lon,
    kind: "approx",
    height_m: NaN,
    point: "Coordinates entered directly; elevation is obtained from the backend DEM.",
    source: "User coordinate",
    url: "",
  }));
}

/** Ticked sites in list order; a coordinate already chosen under another name is evaluated once. */
export function chosenSites(options: Site[], choice: SiteChoice): Site[] {
  const seen = new Set<string>();
  return options.filter((site) => {
    if (!choice.selected.includes(site.id)) return false;
    const key = `${site.lat.toFixed(8)},${(((site.lon % 360) + 360) % 360).toFixed(8)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function SitePicker({
  sites,
  value,
  onChange,
  disabled,
}: {
  sites: Site[];
  value: SiteChoice;
  onChange: (value: SiteChoice) => void;
  disabled: boolean;
}) {
  const { t: tr } = useTranslation();
  // "new" while adding a point; otherwise the id of the custom point being edited.
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState({ lat: NaN, lon: NaN });
  const pointName = (i: number) => tr("Custom point {0}", [i]);
  const toggle = (id: string, on: boolean) =>
    onChange({
      ...value,
      selected: on ? [...value.selected, id] : value.selected.filter((x) => x !== id),
    });
  const position = editing === "new"
    ? value.customs.length + 1
    : value.customs.findIndex((p) => p.id === editing) + 1;
  const valid = validCoordinate(draft.lat, draft.lon);
  const finish = () => {
    if (!valid) return;
    if (editing === "new") {
      const id = `custom-${value.next}`;
      onChange({
        selected: [...value.selected, id],
        customs: [...value.customs, { id, ...draft }],
        next: value.next + 1,
      });
    } else
      onChange({
        ...value,
        customs: value.customs.map((p) => (p.id === editing ? { ...p, ...draft } : p)),
      });
    setEditing(null);
  };
  const remove = (id: string) => {
    onChange({
      ...value,
      selected: value.selected.filter((x) => x !== id),
      customs: value.customs.filter((p) => p.id !== id),
    });
    if (editing === id) setEditing(null);
  };
  const count = value.selected.filter((id) =>
    sites.some((s) => s.id === id) || value.customs.some((p) => p.id === id)).length;
  return (
    <fieldset disabled={disabled} className="space-y-3">
      <legend className="eyebrow mb-2">{tr("Sites to evaluate · {0} selected", [count])}</legend>
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {sites.map((site) => (
          <label key={site.id} className="flex items-center gap-2 text-xs text-soft">
            <input
              type="checkbox"
              aria-label={site.name}
              checked={value.selected.includes(site.id)}
              onChange={(e) => toggle(site.id, e.target.checked)}
            />
            {site.name}
          </label>
        ))}
        {value.customs.map((point, i) =>
          editing === point.id ? null : (
            <span key={point.id} className="flex items-center gap-2 text-xs text-soft">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  aria-label={pointName(i + 1)}
                  checked={value.selected.includes(point.id)}
                  onChange={(e) => toggle(point.id, e.target.checked)}
                />
                {pointName(i + 1)}
              </label>
              <button
                type="button"
                className="font-mono text-[10px] text-mute underline decoration-dotted underline-offset-2 hover:text-white"
                aria-label={tr("Edit {0}", [pointName(i + 1)])}
                onClick={() => {
                  setDraft({ lat: point.lat, lon: point.lon });
                  setEditing(point.id);
                }}
              >
                {coords(point.lat, point.lon, 3)}
              </button>
              <button
                type="button"
                className="px-1 text-mute hover:text-rose"
                aria-label={tr("Remove {0}", [pointName(i + 1)])}
                onClick={() => remove(point.id)}
              >
                ×
              </button>
            </span>
          ),
        )}
      </div>
      {editing ? (
        <form
          className="flex flex-wrap items-end gap-3 border border-line p-3"
          onSubmit={(e) => {
            e.preventDefault();
            finish();
          }}
        >
          <p className="eyebrow w-full">{pointName(position)}</p>
          <div className="grid w-full max-w-md grid-cols-2 gap-3">
            <CoordinateFields
              lat={draft.lat}
              lon={draft.lon}
              layout="row"
              onChange={(lat, lon) => setDraft({ lat, lon })}
            />
          </div>
          <button type="submit" className={actionClass} disabled={!valid}>
            {tr("Done")}
          </button>
          <button
            type="button"
            className="py-2 text-xs text-mute underline underline-offset-2 hover:text-white"
            onClick={() => setEditing(null)}
          >
            {tr("Cancel")}
          </button>
          {!valid && Number.isFinite(draft.lat) && Number.isFinite(draft.lon) && (
            <p role="alert" className="w-full text-xs text-rose">
              {tr("Use a latitude below 90° (S or N) and a longitude up to 180° (E or W).")}
            </p>
          )}
        </form>
      ) : (
        <button
          type="button"
          className="border border-dashed border-line px-3 py-1.5 text-xs text-soft hover:border-white/60 hover:text-white disabled:opacity-40"
          onClick={() => {
            setDraft({ lat: NaN, lon: NaN });
            setEditing("new");
          }}
        >
          {tr("+ Add custom coordinate")}
        </button>
      )}
    </fieldset>
  );
}
