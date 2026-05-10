import "./App.css";

function App() {
  const message = process.env.REACT_APP_MESSAGE || "Hello From React";

  return (
    <div className="App">
      <h1>React Kubernetes Demo</h1>

      <h2>Hello World!</h2>
      <p>{message}</p>

      <p>This app is running inside kubernetes cluster.</p>
    </div>
  );
}

export default App;
