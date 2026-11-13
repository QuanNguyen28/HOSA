import { useTranslation, type Language } from "./LanguageProvider";

function Flag({ language }: { language: Language }) {
  return language === "vi" ? (
    <svg viewBox="0 0 30 20" className="h-4 w-6 sm:h-5 sm:w-[30px]" aria-hidden="true">
      <path fill="#da251d" d="M0 0h30v20H0z" />
      <path fill="#ff0" d="m15 3 1.57 4.84h5.09l-4.12 3 1.57 4.84L15 12.69l-4.11 2.99 1.57-4.84-4.12-3h5.09z" />
    </svg>
  ) : (
    <svg viewBox="0 0 30 20" className="h-4 w-6 sm:h-5 sm:w-[30px]" aria-hidden="true">
      <path fill="#fff" d="M0 0h30v20H0z" />
      {Array.from({ length: 7 }, (_, stripe) => (
        <rect key={stripe} y={stripe * 40 / 13} width="30" height={20 / 13} fill="#b22234" />
      ))}
      <rect width="12" height={140 / 13} fill="#3c3b6e" />
      {Array.from({ length: 9 }, (_, row) =>
        Array.from({ length: row % 2 === 0 ? 6 : 5 }, (_, column) => (
          <path
            key={`${row}-${column}`}
            fill="#fff"
            transform={`translate(${column * 2 + (row % 2 === 0 ? 1 : 2)} ${(row + 1) * 14 / 13}) scale(.45)`}
            d="m0-1 .224.691h.727L.363.118l.225.691L0 .382l-.588.427.225-.691-.588-.427h.727z"
          />
        )),
      )}
    </svg>
  );
}

export function LanguageSwitcher() {
  const { language, setLanguage, t } = useTranslation();
  return (
    <div role="group" aria-label={t("Language")} className="relative isolate flex shrink-0 rounded-md border border-line bg-panel p-1">
      <span
        aria-hidden="true"
        data-testid="language-shading"
        className="pointer-events-none absolute inset-y-1 left-1 -z-10 w-[calc((100%_-_0.5rem)/2)] rounded-sm bg-white/20 shadow-[inset_0_0_0_1px_#ffffff30] transition-transform duration-200 ease-out motion-reduce:transition-none"
        style={{ transform: language === "vi" ? "translateX(100%)" : "translateX(0)" }}
      />
      {(["en", "vi"] as const).map((option) => (
        <button
          key={option}
          type="button"
          lang={option}
          aria-label={option === "en" ? "English" : "Tiếng Việt"}
          title={option === "en" ? "English" : "Tiếng Việt"}
          aria-pressed={language === option}
          onClick={() => setLanguage(option)}
          className={`flex h-8 w-8 min-[360px]:w-9 items-center justify-center rounded-sm transition-opacity sm:w-11 ${language === option ? "opacity-100" : "opacity-50 hover:opacity-100"}`}
        >
          <Flag language={option} />
        </button>
      ))}
    </div>
  );
}
