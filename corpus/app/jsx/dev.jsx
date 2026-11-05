import { renderToStaticMarkup as render } from "react-dom/server";
function App() {
  return <div className="x">
    <b>{1}</b>
    <>
      two
    </>
  </div>;
}
console.log(render(<App />));
