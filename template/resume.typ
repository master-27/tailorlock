// ============================================================================
// LOCKED TEMPLATE — matches the owner's existing LaTeX resume layout:
// Computer Modern serif, small-caps name, steel-blue section titles with a
// rule, en-dash bullets with bold labels, bold key numbers, grouped skills.
// The AI never edits this file (guard hook). Data arrives via sys.inputs.data.
// ============================================================================
#let data = json(bytes(sys.inputs.at("data", default: "{}")))

#set page(paper: "a4", margin: (x: 1.25cm, top: 1.1cm, bottom: 1.0cm))
#set text(font: "New Computer Modern", size: 10pt, fill: black)
#set par(justify: true, leading: 0.5em)

#let accent = rgb("#5b7fa6")
#show link: set text(fill: rgb("#1a4d8f"))

#let section(title) = {
  v(0.45em)
  text(size: 11.5pt, weight: "bold", fill: accent, tracking: 0.03em, upper(title))
  v(-0.75em)
  line(length: 100%, stroke: 0.5pt + black)
  v(-0.3em)
}

// bullet text is pre-escaped by render.py; only *bold* markup survives
#let rich(s) = eval(s, mode: "markup")

#let bullets(items) = {
  for b in items {
    block(spacing: 0.45em, inset: (left: 1.1em))[
      #h(-1.1em)– #h(0.45em)
      #if b.at("label", default: "") != "" [*#b.label:* ]
      #rich(b.text)
    ]
  }
}

#let two(l, r) = grid(columns: (1fr, auto), column-gutter: 1em, l, align(right, r))

// ---------- Header ----------
#let b = data.basics
#align(center)[
  #text(size: 20pt, weight: "regular")[#smallcaps(b.name)]
  #v(-0.6em)
  #text(size: 10pt)[
    #b.phone
    | #link("mailto:" + b.email)[#b.email]
    #for l in b.links [ | #link(l.url)[#l.label] ]
  ]
]

// ---------- Summary ----------
#section("Summary")
#rich(data.summary)

// ---------- Skills (grouped lines, group order = first appearance) ----------
#section("Technical Skills")
#let groups = ()
#let members = (:)
#for s in data.skills {
  if s.group not in members { groups.push(s.group); members.insert(s.group, ()) }
  members.insert(s.group, members.at(s.group) + (s.name,))
}
#for g in groups [
  #block(spacing: 0.35em)[*#g:* #members.at(g).join(", ")]
]

// ---------- Experience ----------
#section("Professional Experience")
#for e in data.experience {
  block(spacing: 0.3em, two(text(weight: "bold", size: 11pt)[#e.role], text(weight: "bold")[#e.start – #e.end]))
  block(spacing: 0.55em, two(emph(e.company), emph(e.location)))
  bullets(e.bullets)
  v(0.25em)
}

// ---------- Projects ----------
#if data.projects.len() > 0 {
  section("Projects")
  for p in data.projects {
    let title = if p.link != "" { link(p.link)[#p.name] } else { [#p.name] }
    block(spacing: 0.3em, text(weight: "bold", size: 11pt, title))
    if p.subtitle != "" or p.stack != "" {
      block(spacing: 0.55em, two(emph(p.subtitle), emph(p.stack)))
    }
    bullets(p.bullets)
    v(0.25em)
  }
}

// ---------- Education ----------
#section("Education")
#for ed in data.education {
  block(spacing: 0.3em, two(text(weight: "bold", size: 11pt)[#ed.institution], text(weight: "bold")[#ed.location]))
  block(spacing: 0.55em, two(emph(ed.degree), emph[#str(ed.start) – #str(ed.end)]))
  if ed.coursework != "" {
    block(spacing: 0.45em)[*Coursework:* #ed.coursework]
  }
}
