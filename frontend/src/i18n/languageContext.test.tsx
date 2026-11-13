import { useContext } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { contextForHotData } from "./languageContext";

describe("language context during hot updates", () => {
  it("connects an existing provider to a newly evaluated consumer module", () => {
    const hotData = {};
    const before = contextForHotData(hotData);
    const after = contextForHotData(hotData);
    function RefreshedConsumer() {
      return <span>{useContext(after).language}</span>;
    }
    const html = renderToStaticMarkup(<before.Provider value={{ language: "vi", setLanguage: () => {} }}>
      <RefreshedConsumer />
    </before.Provider>);
    expect(html).toBe("<span>vi</span>");
    expect(before).toBe(after);
  });

  it("delivers the shared setter rather than an English no-op fallback", () => {
    const hotData = {};
    const provider = contextForHotData(hotData);
    const consumer = contextForHotData(hotData);
    let selected = "vi";
    function Switcher() {
      const value = useContext(consumer);
      value.setLanguage("en");
      return <span>{value.language}</span>;
    }
    renderToStaticMarkup(<provider.Provider value={{ language: "vi", setLanguage: language => { selected = language; } }}>
      <Switcher />
    </provider.Provider>);
    expect(selected).toBe("en");
  });
});
