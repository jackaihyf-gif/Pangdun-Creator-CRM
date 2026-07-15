import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "outputs/cleaning/铭瑄红人记者库_cleaned_review_v2.xlsx";
const previewDir = "outputs/cleaning/previews_v2";
const blob = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(blob);
await fs.mkdir(previewDir, { recursive: true });

const renders = [
  ["怎么确认", "A1:B10"],
  ["Cleaning Summary", "A1:B11"],
  ["人工确认主表", "A1:S35"],
  ["需要处理的问题", "A1:H35"],
];

for (const [sheetName, range] of renders) {
  const png = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const bytes = new Uint8Array(await png.arrayBuffer());
  const safe = sheetName.replace(/[\\/:*?"<>| ]+/g, "_");
  await fs.writeFile(path.join(previewDir, `${safe}.png`), bytes);
}

const inspect = await workbook.inspect({
  kind: "sheet,table",
  maxChars: 2200,
  tableMaxRows: 2,
  tableMaxCols: 5,
});
console.log(JSON.stringify({ workbookPath, previewDir, inspect: inspect.ndjson.slice(0, 1000) }));
