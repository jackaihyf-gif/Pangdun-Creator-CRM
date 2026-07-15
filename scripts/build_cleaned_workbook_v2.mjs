import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataPath = "outputs/cleaning/kol_clean_review_v2.json";
const outputPath = "outputs/cleaning/铭瑄红人记者库_cleaned_review_v2.xlsx";
const data = JSON.parse(await fs.readFile(dataPath, "utf8"));

const workbook = Workbook.create();

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

function matrixFromObjects(rows, headers) {
  return [headers, ...rows.map((row) => headers.map((h) => row[h] ?? ""))];
}

function addTableSheet(name, matrix, tableName, headerFill = "#0F766E") {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const rows = Math.max(matrix.length, 1);
  const cols = Math.max(matrix[0]?.length ?? 1, 1);
  const range = sheet.getRangeByIndexes(0, 0, rows, cols);
  range.values = matrix;
  range.format.font = { name: "Microsoft YaHei", size: 10, color: "#3F3528" };
  range.format.wrapText = true;
  const header = sheet.getRangeByIndexes(0, 0, 1, cols);
  header.format = {
    fill: headerFill,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.freezePanes.freezeRows(1);
  if (rows > 1) {
    const table = sheet.tables.add(`A1:${colName(cols - 1)}${rows}`, true, tableName);
    table.showFilterButton = true;
  }
  range.format.autofitColumns();
  range.format.autofitRows();
  range.format.borders = { preset: "outside", style: "thin", color: "#D7C7A3" };
  return sheet;
}

const guide = workbook.worksheets.add("怎么确认");
guide.showGridLines = false;
guide.getRange("A1:F1").merge();
guide.getRange("A1").values = [["清洗版使用说明"]];
guide.getRange("A1").format = {
  fill: "#0F766E",
  font: { bold: true, color: "#FFFFFF", size: 15 },
};
guide.getRange("A3:B10").values = [
  ["主要看哪张表", "先看“人工确认精简版”。一行就是一个媒体/KOL，空媒体名的原始行已自动归到上一条媒体。"],
  ["action", "可导入 / 确认后导入 / 跳过 / 合并到其他媒体。你只需要改这一列和少量 final 字段。"],
  ["stage_final", "建议阶段。高置信度通常来自“合作情况”；备注里推出来的会标成 Needs Check。"],
  ["product_final", "只是产品线索，不是自动定论。多个产品会标记为 Multiple - review。"],
  ["clean_note_for_crm", "给 CRM 用的精简备注，保留原始上下文但不再塞超长联系方式。"],
  ["Contacts 整理", "联系人仍单独保留，方便后续导入联系人表。"],
  ["Raw 原始数据", "完整保留原始表，作为回溯来源。"],
  ["建议流程", "先筛 action=确认后导入，再修 stage_final/product_final/clean_note_for_crm。"],
];
guide.getRange("A3:B10").format.wrapText = true;
guide.getRange("A:B").format.columnWidth = 34;

const summary = addTableSheet("Cleaning Summary", data.summary, "CleaningSummaryV2", "#2563EB");
summary.getRange("A:B").format.columnWidth = 30;

const compactRows = data.media_review.map((row) => ({
  action: row.action,
  review_reason: row.review_reason,
  media_id: row.media_id,
  media_name_final: row.media_name_final,
  country_final: row.country_final,
  platform_type_final: row.platform_type_final,
  stage_final: row.stage_final,
  product_final: row.product_final,
  clean_note_for_crm: row.clean_note_for_crm,
  source_rows: row.source_rows,
  contacts_count: row.contacts_count,
}));
const compactHeaders = [
  "action",
  "review_reason",
  "media_id",
  "media_name_final",
  "country_final",
  "platform_type_final",
  "stage_final",
  "product_final",
  "clean_note_for_crm",
  "source_rows",
  "contacts_count",
];
const compact = addTableSheet("人工确认精简版", matrixFromObjects(compactRows, compactHeaders), "ManualReviewCompact", "#0F766E");
compact.freezePanes.freezeColumns(4);
compact.getRange("A:A").dataValidation = { rule: { type: "list", values: data.action_options } };
compact.getRange("G:G").dataValidation = { rule: { type: "list", values: data.stage_options } };
compact.getRange("A:B").format.columnWidth = 16;
compact.getRange("D:D").format.columnWidth = 28;
compact.getRange("H:H").format.columnWidth = 22;
compact.getRange("I:I").format.columnWidth = 58;
compact.getRange("J:K").format.columnWidth = 14;

const reviewHeaders = [
  "action",
  "review_reason",
  "media_id",
  "source_rows",
  "media_name_final",
  "country_final",
  "category_final",
  "platform_type_final",
  "website_url_final",
  "followers_or_traffic_final",
  "stage_final",
  "stage_confidence",
  "product_final",
  "product_confidence",
  "contacts_count",
  "deliverable_url_candidate",
  "reference_urls",
  "clean_note_for_crm",
  "raw_stage_note",
];
const main = addTableSheet("人工确认主表", matrixFromObjects(data.media_review, reviewHeaders), "ManualReviewMain", "#047857");
main.freezePanes.freezeColumns(5);
main.getRange("A:A").dataValidation = { rule: { type: "list", values: data.action_options } };
main.getRange("K:K").dataValidation = { rule: { type: "list", values: data.stage_options } };
main.getRange("A:B").format.columnWidth = 16;
main.getRange("E:E").format.columnWidth = 26;
main.getRange("I:I").format.columnWidth = 34;
main.getRange("M:M").format.columnWidth = 24;
main.getRange("P:R").format.columnWidth = 42;
main.getRange("A1:S1").format.rowHeight = 34;

const contactHeaders = [
  "media_id",
  "media_name",
  "source_row",
  "contact_name_final",
  "role_final",
  "email_final",
  "phone_final",
  "telegram_final",
  "whatsapp_final",
  "brief_email_final",
  "press_release_email_final",
  "contact_note",
  "raw_contact_info",
];
const contacts = addTableSheet("Contacts 整理", matrixFromObjects(data.contacts, contactHeaders), "ContactsReviewV2", "#0891B2");
contacts.getRange("D:M").format.columnWidth = 24;
contacts.getRange("M:M").format.columnWidth = 42;

const campaignHeaders = [
  "media_id",
  "media_name",
  "source_rows",
  "stage_final",
  "product_final",
  "brief_sent",
  "quotation_raw",
  "deliverable_url_candidate",
  "campaign_note_final",
];
const campaigns = addTableSheet("Campaign 导入候选", matrixFromObjects(data.campaigns, campaignHeaders), "CampaignReviewV2", "#B45309");
campaigns.getRange("D:D").dataValidation = { rule: { type: "list", values: data.stage_options } };
campaigns.getRange("H:I").format.columnWidth = 44;

const issueHeaders = [
  "media_id",
  "media_name",
  "source_rows",
  "review_reason",
  "suggested_stage",
  "suggested_product",
  "what_to_do",
  "context_excerpt",
];
const issues = addTableSheet("需要处理的问题", matrixFromObjects(data.needs_review, issueHeaders), "IssuesReviewV2", "#B91C1C");
issues.getRange("D:H").format.columnWidth = 38;

const raw = addTableSheet("Raw 原始数据", data.raw_matrix, "RawDataV2", "#6B5A45");
raw.getRange("A:Q").format.columnWidth = 18;

for (const sheetName of ["人工确认精简版", "人工确认主表", "Contacts 整理", "Campaign 导入候选", "需要处理的问题"]) {
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
  tableMaxRows: 2,
  tableMaxCols: 6,
});
console.log(JSON.stringify({ outputPath, inspect: inspect.ndjson.slice(0, 1200) }));
