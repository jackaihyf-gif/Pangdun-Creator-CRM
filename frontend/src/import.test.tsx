import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExecutionImport } from "./main";


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("统一导入中心", () => {
  it("下载标准 CSV 时不导航离开当前页面", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/universal-import/template.csv") {
        return Promise.resolve(new Response("媒体名称*,国家\n", {
          status: 200,
          headers: { "Content-Type": "text/csv" },
        }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:pangdun-template"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    render(<ExecutionImport />);
    await userEvent.click(screen.getByRole("button", { name: "下载标准 CSV" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/universal-import/template.csv",
      { credentials: "include" },
    ));
    expect(anchorClick).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: "统一导入中心" })).toBeVisible();
  });
});
