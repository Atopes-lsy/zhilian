# Product Decisions

Date: 2026-09-09

## Confirmed

- Target user: people with clear learning or growth goals but no systematic method.
- Differentiation: better understanding of Zhihu through high-vote answer quality, comment counterexamples, and preserved author tags.
- Primary output: action list backed by experience summaries.
- Trigger: automatic analysis after the user enters a Zhihu question page, with a lightweight notification.
- Input fields: question, answers, author tags, voteup counts, and comment summaries.
- Quiz: 3 self-test questions by default.
- Feedback: wrong answers create one targeted review flashcard.
- User visibility: ordinary users see final learning results; judge mode shows Agent trace.
- Demo form: simulated Zhihu question page with a right sidebar plugin.
- Author identity display: author tags.
- Comment role: counterexample reminders.
- Action item count: context dependent, typically 3 to 5.

## Implementation Implications

- Replace the current standalone learning workspace with a simulated Zhihu page layout.
- Run the sidebar analysis automatically after page load.
- Show a lightweight notification after automatic analysis.
- Prioritize action items over mind maps or long learning paths.
- Add Zhihu-native fields: `question_title`, `answers[].author_tag`, `answers[].voteup_count`, and `answers[].comment_summary`.
- Move Agent collaboration behind a judge/debug trace toggle.
- Generate exactly 3 quiz questions by default.
- Generate one review flashcard for a wrong answer.
