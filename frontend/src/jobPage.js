// Extension only: reads the job description from the tab the user is on.

// Chrome copies this function into the job page and runs it there, so it
// can't use anything from outside its own body. It tries, in order:
// highlighted text, the page's JobPosting data, known job sites, elements
// named like a job description, and finally the page's main block of text.
// Before reading the page itself, it clicks any "See more" button on the
// description, so users don't have to expand it first.
async function readJobPage() {
  const MIN_LENGTH = 200;
  // Labels of "See more" / "… more" / "Show less" buttons, which some sites
  // place inside the description itself.
  const TOGGLE_LINE = /^(…|\.\.\.)?\s*((see|show|read)\s+)?(more|less)( description)?$/i;
  const TOGGLE_AT_END = /\s*(…|\.\.\.)\s*((see|show|read)\s+)?more$/i;
  const clean = (text) =>
    (text || "")
      .replace(/[ \t\u00a0]+/g, " ")
      .split("\n")
      .map((line) => line.trim().replace(TOGGLE_AT_END, ""))
      .filter((line) => !TOGGLE_LINE.test(line))
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  const join = (...parts) => parts.filter(Boolean).join("\n\n");
  const textOf = (selectors, minLength = 1) => {
    for (const selector of selectors) {
      const text = clean(document.querySelector(selector)?.innerText);
      if (text.length >= minLength) return text;
    }
    return "";
  };

  // 1. Highlighted text wins, so the user can always pick exactly what to use.
  const selection = clean(window.getSelection()?.toString());
  if (selection.length >= 50) return { source: "selection", text: selection };

  // 2. Most job pages embed a JobPosting (schema.org) for Google Jobs, with the
  // full description as HTML. Parsing it with DOMParser never runs scripts.
  const htmlToText = (html) => {
    let text = html || "";
    for (let pass = 0; pass < 2 && /<[a-z/]|&lt;/i.test(text); pass++) {
      const marked = text
        .replace(/<li[^>]*>/gi, "\n- ")
        .replace(/<(br|\/p|\/li|\/h[1-6]|\/div|\/ul|\/ol)[^>]*>/gi, "\n");
      text = new DOMParser().parseFromString(marked, "text/html").body.textContent;
    }
    return clean(text);
  };
  const findPosting = (node) => {
    if (!node || typeof node !== "object") return null;
    if (Array.isArray(node)) return node.map(findPosting).find(Boolean) || null;
    const type = [].concat(node["@type"] || []);
    if (type.includes("JobPosting") && node.description) return node;
    return findPosting(node["@graph"]);
  };
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    let posting = null;
    try {
      posting = findPosting(JSON.parse(script.textContent));
    } catch {
      continue;
    }
    const description = posting && htmlToText(posting.description);
    if (description && description.length >= MIN_LENGTH) {
      const company = [].concat(posting.hiringOrganization || [])[0]?.name;
      return { source: "page", text: join(clean(posting.title), clean(company), description) };
    }
  }

  // Expand truncated descriptions, as if the user clicked "See more". Only
  // buttons (never links, which could navigate away) outside the page's
  // navigation, and only known expand buttons or ones labelled exactly so.
  const EXPAND_BUTTONS = [
    "button.jobs-description__footer-button",
    "button.inline-show-more-text__button",
    "button.show-more-less-html__button--more",
  ];
  const EXPAND_LABEL = /^((…|\.\.\.)\s*|(…|\.\.\.)?\s*(see|show|read)\s+)more( description)?$/i;
  const expandable = [
    ...document.querySelectorAll(EXPAND_BUTTONS.join(", ")),
    ...[...document.querySelectorAll("button, [role='button']:not(a)")].filter((button) =>
      EXPAND_LABEL.test(
        (button.innerText || button.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim(),
      ),
    ),
  ].filter(
    (button) =>
      button.getAttribute("aria-expanded") !== "true" &&
      !button.closest("nav, header, footer, aside, a"),
  );
  if (expandable.length) {
    new Set(expandable).forEach((button) => button.click());
    await new Promise((resolve) => setTimeout(resolve, 400));
  }

  // While reading, hide expand/collapse buttons so labels like "… more" or
  // "Show less" don't end up in the text. They're restored right after.
  const toggles = [...document.querySelectorAll("button, [role='button']")].filter(
    (button) =>
      button.matches(EXPAND_BUTTONS.join(", ")) ||
      TOGGLE_LINE.test(
        (button.innerText || button.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim(),
      ),
  );
  const savedStyles = toggles.map((button) => button.getAttribute("style"));
  toggles.forEach((button) => button.style.setProperty("display", "none", "important"));

  const readPage = () => {
    // 3. Known job sites. They change their markup often, so each part has fallbacks.
    const sites = {
      "linkedin.com": {
        title: [
          ".job-details-jobs-unified-top-card__job-title",
          ".jobs-unified-top-card__job-title",
          ".top-card-layout__title",
        ],
        company: [
          ".job-details-jobs-unified-top-card__company-name",
          ".jobs-unified-top-card__company-name",
          ".topcard__org-name-link",
        ],
        description: [
          "#job-details",
          ".jobs-description__content",
          ".jobs-description-content__text",
          ".description__text",
        ],
      },
      "indeed.com": {
        title: [
          "[data-testid='jobsearch-JobInfoHeader-title']",
          ".jobsearch-JobInfoHeader-title",
        ],
        company: ["[data-testid='inlineHeader-companyName']", "[data-company-name='true']"],
        description: ["#jobDescriptionText"],
      },
      "greenhouse.io": {
        title: [".job__title h1", ".app-title", "h1"],
        company: [".company-name"],
        description: [".job__description", "#content"],
      },
      "lever.co": {
        title: [".posting-headline h2"],
        company: [],
        description: ["[data-qa='job-description']", ".posting-page .content"],
      },
      "myworkdayjobs.com": {
        title: ["[data-automation-id='jobPostingHeader']"],
        company: [],
        description: ["[data-automation-id='jobPostingDescription']"],
      },
      "ashbyhq.com": {
        title: ["h1"],
        company: [],
        description: ["[class*='descriptionText']", "[class*='_description_']"],
      },
      // UKG (UltiPro) careers pages, often linked from LinkedIn's "Apply" button.
      "ultipro.com": {
        title: ["[data-automation='opportunity-title']"],
        company: [],
        description: ["[data-automation='job-description']"],
      },
    };
    const site = Object.keys(sites).find(
      (domain) => location.hostname === domain || location.hostname.endsWith(`.${domain}`),
    );
    if (site) {
      const description = textOf(sites[site].description, MIN_LENGTH);
      if (description) {
        const { title, company } = sites[site];
        return { source: "page", text: join(textOf(title), textOf(company), description) };
      }
    }

    // 4. Elements many careers sites name after the job description.
    const description = textOf(
      [
        "[itemprop='description']",
        "[data-automation*='job-description' i]",
        "[data-testid*='job-description' i]",
        "[id*='job-description' i]",
        "[id*='jobdescription' i]",
        "[class*='job-description' i]",
        "[class*='jobdescription' i]",
        "[class*='job_description' i]",
      ],
      MIN_LENGTH,
    );
    if (description) {
      const title = clean(document.querySelector("h1")?.innerText);
      return { source: "page", text: join(title, description) };
    }

    // 5. The page's main block of text, found the way browser reader modes do:
    // credit each paragraph or bullet's length to its nearby ancestors, then
    // take the best-scoring container that reads like a job posting.
    const JOB_WORDS =
      /responsibilit|qualification|requirement|what you('|’)ll|about the (role|job)|experience with|benefits/i;
    const scores = new Map();
    for (const el of document.querySelectorAll("p, li")) {
      if (el.closest("nav, header, footer, aside")) continue;
      const length = clean(el.textContent).length;
      if (length < 25) continue;
      let ancestor = el.parentElement;
      for (let depth = 0; ancestor && ancestor !== document.body && depth < 4; depth++) {
        scores.set(ancestor, (scores.get(ancestor) || 0) + length / (depth + 1));
        ancestor = ancestor.parentElement;
      }
    }
    const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
    for (const [element] of ranked) {
      const text = clean(element.innerText);
      if (text.length >= MIN_LENGTH && JOB_WORDS.test(text)) {
        const title = clean(document.querySelector("h1")?.innerText);
        return { source: "page", text: text.startsWith(title) ? text : join(title, text) };
      }
    }

    return { source: "none" };
  };

  try {
    return readPage();
  } finally {
    toggles.forEach((button, i) =>
      savedStyles[i] === null
        ? button.removeAttribute("style")
        : button.setAttribute("style", savedStyles[i]),
    );
  }
}

const CANT_READ =
  "Chrome didn't let the extension read this page. Click the extension's toolbar icon " +
  "while on the job page and try again, or copy the description and paste it below.";

// Returns the job text from the current tab, or throws an Error whose message
// tells the user what to do instead.
export async function readCurrentJobPage() {
  const { chrome } = globalThis;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error(CANT_READ);

  let result;
  try {
    [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: readJobPage,
    });
  } catch {
    throw new Error(CANT_READ);
  }

  if (result?.source === "none") {
    throw new Error(
      "Couldn't find a job description on this page. Open the job's own page, or highlight the description and try again.",
    );
  }
  return result.text;
}
