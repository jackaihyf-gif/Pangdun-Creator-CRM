import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "outputs/cleaning/铭瑄红人记者库_cleaned.xlsx";
const previewDir = "outputs/cleaning/previews";

const blob = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(blob);
await fs.mkdir(previewDir, { recursive: true });

const sheetInfo = await workbook.inspect({
  kind: "sheet,table",
  maxChars: 4000,
  tableMaxRows: 2,
  tableMaxCols: 5,
});

const sheetNames = [
  "Cleaning Summary",
  "Raw 原始数据",
  "Media 清洗",
  "Contacts 清洗",
  "Campaign 线索",
  "Needs Review",
];

for (const sheetName of sheetNames) {
  const rendered = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 0.7,
    format: "png",
  });
  const bytes = new Uint8Array(await rendered.arrayBuffer());
  const safeName = sheetName.replace(/[\\/:*?"<>| ]+/g, "_");
  await fs.writeFile(path.join(previewDir, `${safeName}.png`), bytes);
}

console.log(JSON.stringify({
  workbookPath,
  previewDir,
  sheetCount: sheetNames.length,
  inspectSample: sheetInfo.ndjson.slice(0, 1200),
}));
