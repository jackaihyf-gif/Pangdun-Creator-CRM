import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataPath = "outputs/cleaning/cleaned_kol_data.json";
const outputPath = "outputs/cleaning/铭瑄红人记者库_cleaned.xlsx";
const data = JSON.parse(await fs.readFile(dataPath, "utf8"));

const workbook = Workbook.create();

function valuesFromObjects(rows, headers) {
  return [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ""))];
}

function colName(index) {
  let name = "";
  let n = index + 1;
  while (n > 0) {
    const r = (n - 1) % 26;
    name = String.fromCharCode(65 + r) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function addSheet(name, matrix, tableName, options = {}) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const rows = Math.max(matrix.length, 1);
  const cols = Math.max(matrix[0]?.length ?? 1, 1);
  const range = sheet.getRangeByIndexes(0, 0, rows, cols);
  range.values = matrix;
  range.format.wrapText = true;
  range.format.font = { name: "Microsoft YaHei", size: 10, color: "#463829" };
  const header = sheet.getRangeByIndexes(0, 0, 1, cols);
  header.format = {
    fill: options.headerFill ?? "#0F766E",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.freezePanes.freezeRows(1);
  if (rows > 1 && cols > 0) {
    const tableRange = `A1:${colName(cols - 1)}${rows}`;
    const table = sheet.tables.add(tableRange, true, tableName);
    table.showFilterButton = true;
  }
  range.format.autofitColumns();
  range.format.autofitRows();
  sheet.getRangeByIndexes(0, 0, rows, cols).format.borders = {
    preset: "outside",
    style: "thin",
    color: "#D7C7A3",
  };
  return sheet;
}

const mediaHeaders = [
  "media_id",
  "source_rows",
  "name",
  "country",
  "parent_company",
  "category",
  "platform_type",
  "website_url",
  "followers_or_traffic",
  "dedupe_key_type",
  "media_review_note",
];
const contactHeaders = [
  "contact_id",
  "media_id",
  "source_row",
  "media_name",
  "contact_name",
  "contact_role",
  "email",
  "phone",
  "telegram",
  "whatsapp",
  "brief_email",
  "press_release_email",
  "contact_review_note",
  "raw_contact_info",
];
const campaignHeaders = [
  "campaign_lead_id",
  "media_id",
  "source_row",
  "media_name",
  "stage_candidate",
  "stage_confidence",
  "stage_review_note",
  "possible_product_model",
  "product_confidence",
  "product_review_note",
  "quotation_amount",
  "quotation_currency",
  "quotation_review_note",
  "brief_sent",
  "deliverable_url_candidate",
  "reference_urls",
  "clean_notes",
  "raw_cooperation",
  "raw_notes",
  "raw_notes2",
];
const reviewHeaders = [
  "review_id",
  "source_row",
  "media_id",
  "media_name",
  "review_reason",
  "suggested_stage",
  "possible_product_model",
  "original_text",
  "action",
];

const summary = addSheet("Cleaning Summary", data.summary, "CleaningSummaryTable", { headerFill: "#5B8DEF" });
summary.getRange("A1:B1").format.font = { bold: true, color: "#FFFFFF" };
summary.getRange("A:B").format.columnWidth = 28;

const raw = addSheet("Raw 原始数据", data.raw_matrix, "RawDataTable", { headerFill: "#7C6A55" });
raw.getRange("A:Q").format.columnWidth = 18;

const media = addSheet("Media 清洗", valuesFromObjects(data.media, mediaHeaders), "MediaCleanTable");
media.getRange("C:C").format.columnWidth = 24;
media.getRange("H:H").format.columnWidth = 36;

const contacts = addSheet("Contacts 清洗", valuesFromObjects(data.contacts, contactHeaders), "ContactsCleanTable", { headerFill: "#0891B2" });
contacts.getRange("N:N").format.columnWidth = 42;

const campaigns = addSheet("Campaign 线索", valuesFromObjects(data.campaigns, campaignHeaders), "CampaignLeadTable", { headerFill: "#B45309" });
campaigns.getRange("O:P").format.columnWidth = 42;
campaigns.getRange("Q:T").format.columnWidth = 34;
campaigns.getRange("E:E").dataValidation = {
  rule: { type: "list", values: ["", "To Contact", "Contacted", "Waiting Reply", "Quoting", "Brief Sent", "In Production", "Published"] },
};
campaigns.getRange("F:F").dataValidation = {
  rule: { type: "list", values: ["High", "Medium", "Low"] },
};
campaigns.getRange("I:I").dataValidation = {
  rule: { type: "list", values: ["Medium", "Low"] },
};

const review = addSheet("Needs Review", valuesFromObjects(data.review, reviewHeaders), "NeedsReviewTable", { headerFill: "#B91C1C" });
review.getRange("E:H").format.columnWidth = 42;
review.getRange("I:I").dataValidation = {
  rule: { type: "list", values: ["", "确认导入", "修正后导入", "跳过", "合并"] },
};

for (const sheetName of ["Media 清洗", "Contacts 清洗", "Campaign 线索", "Needs Review"]) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const used = sheet.getUsedRange();
  used.format.borders = { preset: "inside", style: "thin", color: "#EFE4CA" };
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

const inspect = await workbook.inspect({
  kind: "sheet,table",
  maxChars: 2500,
  tableMaxRows: 3,
  tableMaxCols: 6,
});
console.log(JSON.stringify({ outputPath, inspect: inspect.ndjson.slice(0, 1200) }));
