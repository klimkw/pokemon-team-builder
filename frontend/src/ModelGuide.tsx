import rawSource from "../../docs/counter-model.md?raw";

const source = rawSource.replace(/\r\n?/g, "\n");

// The guide is trusted repo content. Render a small Markdown subset as React text,
// never HTML, so formulas and code remain safe and readable without a runtime CDN.
export default function ModelGuide() {
  const blocks = source.trim().split(/\n\s*\n/);
  return <main className="model-guide">
    <nav><a href="/">← Team builder</a><a download="counter-model.md" href={`data:text/markdown;charset=utf-8,${encodeURIComponent(source)}`}>Download Markdown</a></nav>
    {blocks.map((block, index) => {
      if (block.startsWith("```")) return <pre key={index}><code>{block.replace(/^```[^\n]*\n/, "").replace(/\n```$/, "")}</code></pre>;
      if (block.startsWith("### ")) return <h3 key={index}>{block.slice(4)}</h3>;
      if (block.startsWith("## ")) return <h2 key={index}>{block.slice(3)}</h2>;
      if (block.startsWith("# ")) return <h1 key={index}>{block.slice(2)}</h1>;
      if (block.startsWith("- ")) return <ul key={index}>{block.split("\n").map((line, i) => <li key={i}>{line.replace(/^- /, "")}</li>)}</ul>;
      return <p key={index}>{block}</p>;
    })}
  </main>;
}
