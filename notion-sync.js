const { Client } = require("@notionhq/client");
const fs = require("fs");
const path = require("path");

const notion = new Client({ auth: process.env.NOTION_API_KEY });

const DATABASE_ID = "3488fff7-e9cf-80d0-a5e7-cb42e8a80cf3";

function parseProjectReadme(folder, content) {
  const nameMatch = content.match(/^# (.+)/m);
  const name = nameMatch ? nameMatch[1].trim() : folder;

  const hasUndone = /- \[ \]/.test(content);
  const hasDone = /- \[x\]/i.test(content);
  let status = "未着手";
  if (hasDone && hasUndone) status = "進行中";
  else if (hasDone && !hasUndone) status = "完了";

  const nextActionMatch = content.match(/- \[ \] (.+)/);
  const nextAction = nextActionMatch ? nextActionMatch[1].trim() : "";

  const assigneeMatch = content.match(/\*\*担当\*\*[：:]\s*(.+)/);
  const assignee = assigneeMatch ? assigneeMatch[1].trim() : "秘書(Claude)";

  const startDateMatch = content.match(/\*\*開始日\*\*[：:]\s*(\d{4}-\d{2}-\d{2})/);
  const startDate = startDateMatch ? startDateMatch[1] : null;

  const summaryMatch = content.match(/## 概要\n+(.+)/);
  const summary = summaryMatch ? summaryMatch[1].trim() : "";

  return { name, status, nextAction, assignee, startDate, summary };
}

function buildProperties(project) {
  const props = {
    プロジェクト名: {
      title: [{ text: { content: project.name } }],
    },
    ステータス: {
      status: { name: project.status },
    },
    優先度: {
      select: { name: "中" },
    },
    担当: {
      select: { name: project.assignee },
    },
    次のアクション: {
      rich_text: [{ text: { content: project.nextAction } }],
    },
    概要: {
      rich_text: [{ text: { content: project.summary } }],
    },
  };

  if (project.startDate) {
    props["開始日"] = { date: { start: project.startDate } };
  }

  return props;
}

async function getExistingPages() {
  const res = await notion.databases.query({ database_id: DATABASE_ID });
  const byName = {};
  for (const page of res.results) {
    const titleProp = page.properties?.プロジェクト名;
    const text = titleProp?.title?.[0]?.plain_text;
    if (text) byName[text] = page.id;
  }
  return byName;
}

async function sync() {
  const projectsDir = path.join(__dirname, "projects");
  const folders = fs
    .readdirSync(projectsDir)
    .filter((f) => fs.statSync(path.join(projectsDir, f)).isDirectory());

  const localProjects = folders.map((folder) => {
    const readmePath = path.join(projectsDir, folder, "README.md");
    const content = fs.existsSync(readmePath)
      ? fs.readFileSync(readmePath, "utf-8")
      : "";
    return parseProjectReadme(folder, content);
  });

  console.log(`Found ${localProjects.length} local project(s).`);

  const existingByName = await getExistingPages();

  for (const project of localProjects) {
    const properties = buildProperties(project);
    if (existingByName[project.name]) {
      await notion.pages.update({
        page_id: existingByName[project.name],
        properties,
      });
      console.log(`Updated: ${project.name} → ${project.status}`);
    } else {
      await notion.pages.create({
        parent: { database_id: DATABASE_ID },
        properties,
      });
      console.log(`Created: ${project.name} → ${project.status}`);
    }
  }

  console.log("Sync complete.");
}

sync().catch((e) => {
  console.error("Sync failed:", e.message);
  process.exit(1);
});
