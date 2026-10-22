import { Fragment } from "react";
import rawSource from "../../docs/architecture.md?raw";
import "./architecture-guide.css";

const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

const source = rawSource.replace(/\r\n?/g, "\n");

// Only repository-authored text is supported. No raw HTML or runtime Markdown execution.
function inline(value: string) {
  return value.split(/(`[^`]+`|\[[^\]\n]+\]\((?:https:\/\/[^\s)]+|counter-model\.md)\))/g).map((part, index) => {
    if (part.startsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    // Allow HTTPS references and the repository calculation guide; other markup stays plain text.
    const link = part.match(/^\[([^\]\n]+)\]\(((?:https:\/\/[^\s)]+|counter-model\.md))\)$/);
    if (link?.[2] === "counter-model.md") return <a key={index} href="/counter-method">{link[1]}</a>;
    if (link) return <a key={index} href={link[2]} target="_blank" rel="noopener noreferrer">{link[1]}</a>;
    return <Fragment key={index}>{part}</Fragment>;
  });
}

function blocks(markdown: string) {
  // Keep blank lines inside code fences; the existing calculation guide has a smaller grammar.
  return markdown.match(/```[^\n]*\n[\s\S]*?```|[^\n]+(?:\n(?!\s*\n)[^\n]+)*/g) ?? [];
}

export default function ArchitectureGuide() {
  const sections = [...source.matchAll(/^## (.+)$/gm)].map(match => match[1]);
  return <main className="architecture-guide">
    <nav className="architecture-toolbar" aria-label="Documentation navigation">
      <a href="/">← Team builder</a>
      <a href="/counter-method">Calculation guide</a>
      <a download="architecture.md" href={`data:text/markdown;charset=utf-8,${encodeURIComponent(source)}`}>Download Markdown</a>
    </nav>
    <div className="architecture-layout">
      <aside className="architecture-outline"><nav aria-label="On this page"><strong>On this page</strong><ol>
        {sections.map(title => <li key={title}><a href={`#${slug(title)}`}>{title.replace(/^\d+ /, "")}</a></li>)}
      </ol></nav></aside>
      <article>
        {blocks(source.trim()).map((block, index) => {
          if (block.startsWith("```")) return <pre key={index}><code>{block.replace(/^```[^\n]*\n/, "").replace(/\n```$/, "")}</code></pre>;
          const heading = block.match(/^(#{1,3}) (.+)$/);
          if (heading) {
            const title = heading[2], id = slug(title);
            if (heading[1].length === 1) return <h1 id={id} key={index}>{title}</h1>;
            if (heading[1].length === 2) return <h2 id={id} key={index}>{title}</h2>;
            return <h3 id={id} key={index}>{title}</h3>;
          }
          const picture = block.match(/^!\[([^\]]+)\]\(\.\.\/frontend\/public\/(architecture\.svg)\)$/);
          if (picture) return <figure key={index}><a href={`/${picture[2]}`} target="_blank" rel="noreferrer" aria-label="Open full architecture diagram"><img src={`/${picture[2]}`} alt={picture[1]} /></a><figcaption>Open the diagram for a larger view. <a href={`/${picture[2]}`} download="architecture.svg">Download SVG</a></figcaption></figure>;
          if (block.startsWith("|")) {
            const rows = block.split("\n").map(line => line.slice(1, -1).split("|").map(cell => cell.trim()));
            return <div className="architecture-table" role="region" aria-label={`${rows[0][0]} comparison`} tabIndex={0} key={index}><table>
              <thead><tr>{rows[0].map((cell, i) => <th scope="col" key={i}>{inline(cell)}</th>)}</tr></thead>
              <tbody>{rows.slice(2).map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{inline(cell)}</td>)}</tr>)}</tbody>
            </table></div>;
          }
          if (/^\d+\. /.test(block)) return <ol key={index}>{block.split("\n").map((line, i) => <li key={i}>{inline(line.replace(/^\d+\. /, ""))}</li>)}</ol>;
          return <p key={index}>{inline(block)}</p>;
        })}
      </article>
    </div>
  </main>;
}
