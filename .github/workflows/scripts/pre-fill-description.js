// @ts-check

/**
 * @param {Omit<import('@actions/github-script').AsyncFunctionArguments, 'github'> & { github: import('@actions/github').GitHub }} args
 */
module.exports = async ({ github, context }) => {
  const prNumber = context.issue.number;
  const owner = context.repo.owner;
  const repo = context.repo.repo;

  /** @type {any[]} */
  let commits;

  /** @type {string} */
  let currentBody;

  // 1. Get all commits in this Pull Request
  if (process.env.ACT) {
    // 1. Локальный запуск через утилиту act — берем данные из нашего pull_request.json
    const payload = context.payload;
    commits = payload["mock_commits"] || [];
    currentBody = payload["pull_request"]?.["body"] || "";
  } else {
    // 2. Продакшен режим на реальном сервере GitHub — делаем стандартные сетевые запросы
    const { data: fetchedCommits } = await github.rest.pulls.listCommits({
      owner,
      repo,
      pull_number: prNumber,
    });
    const { data: currentPr } = await github.rest.pulls.get({
      owner,
      repo,
      pull_number: prNumber,
    });
    commits = fetchedCommits;
    currentBody = currentPr.body || "";
  }

  const commitHistory = commits
    .map((c) => {
      const commitObj = c["commit"];
      const authorObj = c["author"];

      const commitMessage =
        commitObj && commitObj["message"] ? commitObj["message"].split("\n")[0] : "No message";

      let authorName = "unknown";
      if (authorObj && authorObj["login"]) {
        authorName = authorObj["login"];
      } else if (commitObj && commitObj["author"] && commitObj["author"]["name"]) {
        authorName = commitObj["author"]["name"];
      }

      return `* ${commitMessage} (by @${authorName})`;
    })
    .join("\n");

  // 4. Inject the commit history into the ## Description section
  const targetSection = "## Description";
  if (currentBody.includes(targetSection)) {
    currentBody = currentBody.replace(
      targetSection,
      `${targetSection}\n<!-- Automatically gathered commit history. Feel free to adapt or rewrite: -->\n### Commit History:\n${commitHistory}\n`
    );
  }

  // 5. Update the Pull Request body (тоже оборачиваем в проверку, чтобы локально не спамить в сеть)
  if (!process.env.ACT) {
    await github.rest.pulls.update({
      owner,
      repo,
      pull_number: prNumber,
      body: currentBody,
    });
  } else {
    console.log("🚀 [Local ACT Mode] Successfully generated new PR Body:");
    console.log(currentBody);
  }
};
