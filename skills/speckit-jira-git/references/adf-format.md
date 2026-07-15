# Atlassian Document Format (ADF) primer

Jira Cloud rejects plain strings in any rich-text field (`description`,
`comment.body`, `worklog.comment`). Pass an ADF document instead.

## Top-level shape

```json
{
  "type": "doc",
  "version": 1,
  "content": [ <block nodes> ]
}
```

`content` is an array of block-level nodes. The skill uses a small subset:
paragraphs, headings, bullet lists, and inline code marks.

## Block nodes

### Paragraph

```json
{
  "type": "paragraph",
  "content": [
    {"type": "text", "text": "Plain sentence."}
  ]
}
```

### Heading

```json
{
  "type": "heading",
  "attrs": {"level": 3},
  "content": [{"type": "text", "text": "Section title"}]
}
```

`level` is 1-6.

### Bullet list

```json
{
  "type": "bulletList",
  "content": [
    {
      "type": "listItem",
      "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "First item"}]}
      ]
    },
    {
      "type": "listItem",
      "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Second item"}]}
      ]
    }
  ]
}
```

Numbered lists swap `bulletList` for `orderedList`. Same item structure.

## Inline marks

A text node can carry marks. The skill uses `code` for inline code:

```json
{"type": "text", "text": "compute_health_transition", "marks": [{"type": "code"}]}
```

Other marks Jira accepts: `strong`, `em`, `underline`, `strike`, `subsup`,
`textColor`, `link`. Avoid `link` unless you need it; URLs in plain text
become click-through links automatically.

## Composing a comment

Pattern from the skill:

```python
from jira_client import JiraClient

doc = JiraClient.adf_doc([
    JiraClient.adf_heading("Phase 1 Setup, done", level=4),
    JiraClient.adf_para("One-paragraph summary of what shipped."),
    JiraClient.adf_heading("Done", level=5),
    JiraClient.adf_bullet_list([
        "T001: short description.",
        "T002: short description.",
    ]),
    JiraClient.adf_para("Commit: <sha> on <branch>."),
])
```

The result is the `body` field of a comment POST or `description` field of
an issue create.

## Markdown to ADF

The skill ships `scripts/markdown_to_adf.py`, which converts a small
markdown subset (paragraphs, headings, bullet lists, inline code) into ADF.
That's enough for the comment / worklog / description bodies the skill
needs. Anything more elaborate should be hand-built using the helpers in
`jira_client.py`.

## Things to avoid

| Don't | Why | Substitute |
|---|---|---|
| Em-dashes | The skill defaults strip these; the wider style guide also avoids them. | Period and new sentence; comma; or hyphen. |
| Plain backticks in `text` nodes | They render as literal characters, not as inline code. | Use the `code` mark on a separate text node. |
| Nested lists | The minimal converter does not produce them, and rendering varies across Jira UI versions. | Promote sub-bullets to follow-up paragraphs. |
| Markdown tables | Atlassian uses a different table node. Hand-build it if you need one. | Bullet list with `field: value` items. |
