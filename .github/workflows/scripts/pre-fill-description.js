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
    const payload = context.payload;
    commits = payload["mock_commits"] || [];
    currentBody = payload["pull_request"]?.["body"] || "";
  } else {
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
  const startMarker = "<!-- START_COMMIT_HISTORY -->";
  const endMarker = "<!-- END_COMMIT_HISTORY -->";
  const targetSection = "## Description";

  const newHistoryBlock = `${startMarker}\n<!-- Automatically gathered commit history. Feel free to adapt or rewrite: -->\n### Commit History:\n${commitHistory}\n${endMarker}`;

  if (currentBody.includes(startMarker) && currentBody.includes(endMarker)) {
    const regex = new RegExp(`${startMarker}[\\s\\S]*?${endMarker}`);
    currentBody = currentBody.replace(regex, newHistoryBlock);
  } else if (currentBody.includes(targetSection)) {
    currentBody = currentBody.replace(targetSection, `${targetSection}\n${newHistoryBlock}`);
  }

  // 5. Update the Pull Request body
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
