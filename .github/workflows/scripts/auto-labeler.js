// @ts-check

// --- UNICODE EMOJI CONSTANTS (Safe for ESLint & Cross-platform encoding) ---
const EMOJI_SEC = "\uD83D\uDEE1\uFE0F"; // 🛡️
const EMOJI_FEAT = "\uD83D\uDE80"; // 🚀
const EMOJI_BUG = "\uD83D\uDC1E"; // 🐞
const EMOJI_REVERT = "\u23EA"; // ⏪
const EMOJI_PERF = "\u26A1"; // ⚡
const EMOJI_DOCS = "\uD83D\uDCDD"; // 📝
const EMOJI_CI = "\uD83E\uDD16"; // 🤖
const EMOJI_TEST = "\uD83E\uDDEA"; // 🧪
const EMOJI_BUILD = "\uD83D\uDCE6"; // 📦
const EMOJI_STYLE = "\uD83C\uDFA8"; // 🎨
const EMOJI_REFACTOR = "\u267B\uFE0F"; // ♻️
const EMOJI_CHORE = "\u2699\uFE0F"; // ⚙️
const EMOJI_BREAK = "\uD83D\uDEA8"; // 🚨
const EMOJI_WARNING = "\u26A0\uFE0F"; // ⚠️

// --- MANAGED GITHUB LABEL NAMES ---
const LABEL_SEC = `${EMOJI_SEC} sec`;
const LABEL_FEAT = `${EMOJI_FEAT} feat`;
const LABEL_BUGFIX = `${EMOJI_BUG} fix`;
const LABEL_REVERT = `${EMOJI_REVERT} revert`;
const LABEL_PERF = `${EMOJI_PERF} perf`;
const LABEL_DOCS = `${EMOJI_DOCS} docs`;
const LABEL_CI = `${EMOJI_CI} ci`;
const LABEL_TEST = `${EMOJI_TEST} test`;
const LABEL_BUILD = `${EMOJI_BUILD} build`;
const LABEL_STYLE = `${EMOJI_STYLE} style`;
const LABEL_REFACTOR = `${EMOJI_REFACTOR} refactor`;
const LABEL_CHORE = `${EMOJI_CHORE} chore`;
const LABEL_BREAKING = `${EMOJI_BREAK} break`;

// --- REGULAR EXPRESSION PATTERNS ---
// Matches any line starting with a checked Markdown checkbox like "- [x]" or "  - [X]"
const CHECKBOX_LINE_REGEX = /^\s*-\s*\[[xX]]/;
// Isolates the "Breaking Changes" section Markdown block until the next header or EOF
const BREAKING_SECTION_REGEX = /##\s*[\s\S]*?Breaking Changes[\s\S]*?(?=##|$)/i;
// Validates if a checked Markdown checkbox exists anywhere within a given multiline string
const CHECKED_BOX_EXISTS_REGEX = /^\s*-\s*\[[xX]]/im;

/**
 * @param {Omit<import('@actions/github-script').AsyncFunctionArguments, 'github'> & { github: import('@actions/github').GitHub, core: any }} args
 */
module.exports = async ({ github, context, core }) => {
  if (!context.payload["pull_request"]) {
    console.log("No pull request found in context.");
    return;
  }

  /** @type {import('@octokit/webhooks-types').PullRequestEvent} */
  const payload = /** @type {any} */ (context.payload);

  const prNumber = payload.pull_request.number;
  const prBody = payload.pull_request.body || "";

  console.log(`Processing PR #${prNumber} based on template checkboxes.`);

  // 1. Setup Label Mappings based on checkbox text
  const labelMapping = {
    "Security Update": LABEL_SEC,
    "New Feature": LABEL_FEAT,
    "Bug Fix": LABEL_BUGFIX,
    Revert: LABEL_REVERT,
    "Performance Improvement": LABEL_PERF,
    Documentation: LABEL_DOCS,
    "CI/CD & Tooling": LABEL_CI,
    Test: LABEL_TEST,
    "Build System or external dependencies": LABEL_BUILD,
    Style: LABEL_STYLE,
    Refactor: LABEL_REFACTOR,
    Maintenance: LABEL_CHORE,
  };

  // 2. Parse Standard Semantic Type Checkboxes (Bulletproof line-by-line keyword parsing)
  const prBodyLines = prBody.split(/\r?\n/);
  /** @type {string[]} */
  const detectedLabels = [];

  const keywordToLabel = {
    security: LABEL_SEC,
    feature: LABEL_FEAT,
    "bug fix": LABEL_BUGFIX,
    bugfix: LABEL_BUGFIX,
    revert: LABEL_REVERT,
    performance: LABEL_PERF,
    documentation: LABEL_DOCS,
    docs: LABEL_DOCS,
    "ci/cd": LABEL_CI,
    tooling: LABEL_CI,
    test: LABEL_TEST,
    "build system": LABEL_BUILD,
    dependencies: LABEL_BUILD,
    style: LABEL_STYLE,
    refactor: LABEL_REFACTOR,
    maintenance: LABEL_CHORE,
    chore: LABEL_CHORE,
  };

  for (const line of prBodyLines) {
    if (CHECKBOX_LINE_REGEX.test(line)) {
      const lowerLine = line.toLowerCase();
      for (const [keyword, mappedLabel] of Object.entries(keywordToLabel)) {
        if (lowerLine.includes(keyword)) {
          if (!detectedLabels.includes(mappedLabel)) {
            detectedLabels.push(mappedLabel);
          }
          break;
        }
      }
    }
  }

  // 3. Parse Breaking Changes Section strictly by a single checkbox (Emoji-free)
  const breakingSectionMatch = prBody.match(BREAKING_SECTION_REGEX);

  if (breakingSectionMatch) {
    const breakingContent = breakingSectionMatch[0];
    if (CHECKED_BOX_EXISTS_REGEX.test(breakingContent)) {
      detectedLabels.push(LABEL_BREAKING);
    }
  }

  console.log("Detected labels (including breaking):", detectedLabels);

  // 4. Manage GitHub Labels via API
  const { data: existingLabels } = await github.rest.issues.listLabelsOnIssue({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: prNumber,
  });

  const existingLabelNames = existingLabels.map((l) => l.name);
  const allManagedLabels = [...Object.values(labelMapping), LABEL_BREAKING];

  // Remove outdated labels
  for (const label of existingLabelNames) {
    if (allManagedLabels.includes(label) && !detectedLabels.includes(label)) {
      try {
        await github.rest.issues.removeLabel({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: prNumber,
          name: label,
        });
        console.log(`Removed outdated label: ${label}`);
      } catch (e) {
        // @ts-ignore
        console.log(`Failed to remove label ${label}: ${e.message}`);
      }
    }
  }

  // Add newly checked labels
  for (const targetLabel of detectedLabels) {
    if (!existingLabelNames.includes(targetLabel)) {
      console.log(`Adding label: "${targetLabel}"`);
      await github.rest.issues.addLabels({
        issue_number: prNumber,
        owner: context.repo.owner,
        repo: context.repo.repo,
        labels: [targetLabel],
      });
    }
  }

  // 5. Fetch all comments to manage validation logs
  const { data: comments } = await github.rest.issues.listComments({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: prNumber,
  });

  // 6. Validate that at least one semantic type was selected
  const selectedTypes = detectedLabels.filter((l) => l !== LABEL_BREAKING);
  const validationComment = comments.find(
    (comment) =>
      comment.user?.type?.toLowerCase() === "bot" &&
      comment.body?.includes("Please select at least one Type of Change")
  );

  if (selectedTypes.length === 0) {
    const warningMessage = `## ${EMOJI_WARNING} Action Required: Missing Change Type\n\n@${payload.pull_request.user.login}, please select at least one **Type of Change** in your PR description checkboxes so that we can properly categorize this change and update the PR title.`;

    if (!validationComment) {
      console.log("No validation comment found. Creating a new one.");
      await github.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: prNumber,
        body: warningMessage,
      });
    }

    core.setFailed("Validation failed: No 'Type of Change' was selected in the PR description.");
    return;
  }

  // If validation passes, clean up any old warning comments
  if (validationComment) {
    console.log(`Deleting old type-validation comment with ID: ${validationComment.id}`);
    await github.rest.issues.deleteComment({
      owner: context.repo.owner,
      repo: context.repo.repo,
      comment_id: validationComment.id,
    });
  }

  // 7. Delete old bot validation comments (release notes warning)
  const botComment = comments.find(
    (comment) =>
      comment.user?.type?.toLowerCase() === "bot" &&
      comment.body?.includes("automated release notes generation")
  );

  if (botComment) {
    console.log(`Deleting old validation comment with ID: ${botComment.id}`);
    await github.rest.issues.deleteComment({
      owner: context.repo.owner,
      repo: context.repo.repo,
      comment_id: botComment.id,
    });
  }
};
