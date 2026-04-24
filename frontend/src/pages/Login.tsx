export default function Login() {
  return (
    <div style={{ padding: "40px", fontFamily: "Arial", maxWidth: "400px", margin: "100px auto" }}>
      <h1 style={{ marginBottom: "20px" }}>Login Sotel Fit</h1>
      <input type="email" placeholder="Email" style={{ display: "block", width: "100%", padding: "8px", marginBottom: "10px" }} />
      <input type="password" placeholder="Senha" style={{ display: "block", width: "100%", padding: "8px", marginBottom: "10px" }} />
      <button style={{ width: "100%", padding: "10px", background: "#2563eb", color: "white", border: "none", cursor: "pointer" }}>Entrar</button>
    </div>
  );
}