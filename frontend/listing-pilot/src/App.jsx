import { useState, useEffect, useCallback } from "react";

// ---------------------------------------------------------------------------
// Config — change this to your backend URL
// ---------------------------------------------------------------------------
const API_BASE = window.location.hostname === "localhost"
  ? "http://localhost:8000"
  : "https://apicore.ntotech.top";  // ← replace with your real API domain


const GOOGLE_CLIENT_ID = "343640572950-0jokd92mui2lqjqmv2r8rr57vgjdqb2v.apps.googleusercontent.com"; // ← replace

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------
async function api(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail?.message || data.detail || `Error ${res.status}`);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const PLATFORMS = [
  { id: "amazon", label: "Amazon", icon: "📦" },
  { id: "shopify", label: "Shopify", icon: "🛍" },
  { id: "etsy", label: "Etsy", icon: "✨" },
  { id: "ebay", label: "eBay", icon: "🏷" },
];
const TONES = [
  { id: "professional", label: "Professional" },
  { id: "friendly", label: "Friendly" },
  { id: "luxury", label: "Luxury" },
  { id: "technical", label: "Technical" },
];

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------
const font = "'DM Sans', sans-serif";
const monoFont = "'Space Mono', monospace";
const blue = "#2563eb";
const darkBlue = "#1d4ed8";
const darkBg = "#0f172a";

const inputBase = {
  width: "100%",
  padding: "12px 16px",
  fontSize: "14px",
  border: "1.5px solid #e2e8f0",
  borderRadius: "10px",
  outline: "none",
  fontFamily: font,
  color: "#1e293b",
  background: "#fff",
  transition: "border-color 0.2s",
  boxSizing: "border-box",
};
const labelBase = {
  fontSize: "13px", fontWeight: 600, color: "#334155",
  marginBottom: "6px", display: "block", fontFamily: font,
};
const cardStyle = {
  background: "#fff", borderRadius: "16px", padding: "28px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 6px 24px rgba(0,0,0,0.03)",
};
const btnPrimary = {
  padding: "12px 24px", fontSize: "14px", fontWeight: 700,
  background: `linear-gradient(135deg, ${blue} 0%, ${darkBlue} 100%)`,
  color: "#fff", border: "none", borderRadius: "10px", cursor: "pointer",
  fontFamily: font, boxShadow: "0 4px 14px rgba(37,99,235,0.3)", width: "100%",
};

// ---------------------------------------------------------------------------
// CopyButton
// ---------------------------------------------------------------------------
function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false);
  return (
    <button onClick={() => {
      navigator.clipboard.writeText(text); setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }} style={{
      padding: "5px 12px", fontSize: "12px",
      background: copied ? "#059669" : "transparent",
      color: copied ? "#fff" : "#64748b",
      border: copied ? "none" : "1px solid #e2e8f0",
      borderRadius: "6px", cursor: "pointer", fontFamily: font,
      transition: "all 0.2s",
    }}>
      {copied ? "✓ Copied" : (label || "Copy")}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Section block
// ---------------------------------------------------------------------------
function Section({ label, children, copyText }) {
  return (
    <div style={{ marginBottom: "20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "#94a3b8" }}>{label}</span>
        {copyText && <CopyButton text={copyText} />}
      </div>
      <div style={{
        background: "#f8fafc", borderRadius: "8px", padding: "16px",
        fontSize: "14px", lineHeight: 1.7, color: "#1e293b",
        border: "1px solid #f1f5f9", fontFamily: font, whiteSpace: "pre-wrap",
      }}>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Auth Screen
// ---------------------------------------------------------------------------
function AuthScreen({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);

  // Load Google Identity Services script
  useEffect(() => {
    if (document.getElementById("google-gsi")) {
      setGoogleReady(true);
      return;
    }
    const script = document.createElement("script");
    script.id = "google-gsi";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => setGoogleReady(true);
    document.head.appendChild(script);
  }, []);

  // Initialize Google button once script is ready
  useEffect(() => {
    if (!googleReady || !window.google?.accounts?.id) return;
    if (!GOOGLE_CLIENT_ID || GOOGLE_CLIENT_ID.includes("your-google")) return;

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response) => {
        setError(""); setLoading(true);
        try {
          const data = await api("/auth/google", {
            method: "POST",
            body: { credential: response.credential },
          });
          onLogin(data.token, data.user);
        } catch (e) {
          setError(e.message);
        } finally {
          setLoading(false);
        }
      },
    });

    const btnContainer = document.getElementById("google-btn");
    if (btnContainer) {
      btnContainer.innerHTML = "";
      window.google.accounts.id.renderButton(btnContainer, {
        type: "standard",
        theme: "outline",
        size: "large",
        width: "352",
        text: "continue_with",
        shape: "rectangular",
        logo_alignment: "center",
      });
    }
  }, [googleReady, isLogin, onLogin]);

  const handleSubmit = async () => {
    setError(""); setLoading(true);
    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const data = await api(endpoint, { method: "POST", body: { email, password } });
      onLogin(data.token, data.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", background: "#f0f4f8", display: "flex",
      alignItems: "center", justifyContent: "center", fontFamily: font,
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@700&display=swap" rel="stylesheet" />
      <div style={{ width: "100%", maxWidth: "400px", padding: "24px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <h1 style={{ margin: 0, fontSize: "28px", fontFamily: monoFont, color: darkBg }}>
            <span style={{ color: blue }}>◆</span> ListingPilot
          </h1>
          <p style={{ color: "#64748b", fontSize: "14px", marginTop: "8px" }}>
            One input → listings for every platform
          </p>
        </div>

        <div style={cardStyle}>
          {/* Tabs */}
          <div style={{ display: "flex", marginBottom: "24px", borderBottom: "2px solid #f1f5f9" }}>
            {[{ key: true, label: "Log In" }, { key: false, label: "Sign Up" }].map(t => (
              <button key={String(t.key)} onClick={() => { setIsLogin(t.key); setError(""); }}
                style={{
                  flex: 1, padding: "10px", fontSize: "14px", fontWeight: isLogin === t.key ? 700 : 500,
                  color: isLogin === t.key ? darkBlue : "#64748b", background: "transparent",
                  border: "none", borderBottom: isLogin === t.key ? `2px solid ${blue}` : "2px solid transparent",
                  cursor: "pointer", fontFamily: font, marginBottom: "-2px",
                }}>{t.label}</button>
            ))}
          </div>

          <div style={{ display: "grid", gap: "16px" }}>
            <div>
              <label style={labelBase}>Email</label>
              <input type="email" style={inputBase} placeholder="you@example.com"
                value={email} onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmit()} />
            </div>
            <div>
              <label style={labelBase}>Password</label>
              <input type="password" style={inputBase}
                placeholder={isLogin ? "Your password" : "At least 6 characters"}
                value={password} onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmit()} />
            </div>

            {error && (
              <div style={{
                padding: "10px 14px", borderRadius: "8px", fontSize: "13px",
                background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca",
              }}>{error}</div>
            )}

            <button onClick={handleSubmit} disabled={loading || !email || !password}
              style={{
                ...btnPrimary,
                opacity: (loading || !email || !password) ? 0.6 : 1,
                cursor: (loading || !email || !password) ? "not-allowed" : "pointer",
              }}>
              {loading ? "Please wait..." : isLogin ? "Log In" : "Create Account"}
            </button>

            {/* Divider */}
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={{ flex: 1, height: "1px", background: "#e2e8f0" }} />
              <span style={{ fontSize: "12px", color: "#94a3b8" }}>or</span>
              <div style={{ flex: 1, height: "1px", background: "#e2e8f0" }} />
            </div>

            {/* Google Sign-In */}
            <div id="google-btn" style={{ display: "flex", justifyContent: "center", minHeight: "44px" }}>
              {!googleReady && (
                <span style={{ fontSize: "13px", color: "#94a3b8" }}>Loading Google Sign-In...</span>
              )}
            </div>
          </div>
        </div>

        <p style={{ textAlign: "center", fontSize: "12px", color: "#94a3b8", marginTop: "16px" }}>
          Free account includes 3 generations per day
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result Panel for each platform
// ---------------------------------------------------------------------------
function ResultPanel({ data }) {
  if (!data || data.error) {
    return <div style={{ color: "#dc2626", padding: "16px" }}>{data?.error || "No data"}</div>;
  }

  const d = data.data;
  const allText = [
    d.title, d.bullets?.join("\n"), d.description,
    d.seo ? `${d.seo.metaTitle}\n${d.seo.metaDesc}` : "",
    d.tags?.join(", "),
    d.itemSpecifics ? Object.entries(d.itemSpecifics).map(([k, v]) => `${k}: ${v}`).join("\n") : "",
  ].filter(Boolean).join("\n\n");

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "16px" }}>
        <CopyButton text={allText} label="Copy All" />
      </div>

      {d.title && <Section label="Title" copyText={d.title}>{d.title}</Section>}

      {d.bullets && (
        <Section label="Bullet Points" copyText={d.bullets.join("\n")}>
          {d.bullets.map((b, i) => <div key={i} style={{ marginBottom: i < d.bullets.length - 1 ? 12 : 0 }}>{b}</div>)}
        </Section>
      )}

      {d.description && <Section label="Description" copyText={d.description}>{d.description}</Section>}

      {d.seo && (
        <Section label="SEO Meta" copyText={`${d.seo.metaTitle}\n${d.seo.metaDesc}`}>
          <div><strong style={{ color: blue }}>Title:</strong> {d.seo.metaTitle}</div>
          <div style={{ marginTop: 6 }}><strong style={{ color: blue }}>Description:</strong> {d.seo.metaDesc}</div>
        </Section>
      )}

      {d.tags && (
        <Section label="Tags" copyText={d.tags.join(", ")}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {d.tags.map((t, i) => (
              <span key={i} style={{
                background: "#e0f2fe", color: "#0369a1", padding: "4px 10px",
                borderRadius: "99px", fontSize: "12px", fontWeight: 500,
              }}>{t}</span>
            ))}
          </div>
        </Section>
      )}

      {d.itemSpecifics && (
        <Section label="Item Specifics" copyText={Object.entries(d.itemSpecifics).map(([k, v]) => `${k}: ${v}`).join("\n")}>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 16px" }}>
            {Object.entries(d.itemSpecifics).map(([k, v]) => (
              <div key={k} style={{ display: "contents" }}>
                <span style={{ fontWeight: 600, color: "#475569" }}>{k}</span>
                <span>{v}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main App (after login)
// ---------------------------------------------------------------------------
function MainApp({ token, user: initUser, onLogout }) {
  const [user, setUser] = useState(initUser);
  const [usage, setUsage] = useState(null);
  const [paymentConfig, setPaymentConfig] = useState(null);

  useEffect(() => {
    api("/config").then(setPaymentConfig).catch(() => {});
  }, []);

  // Load PayPal SDK when provider is paypal
  useEffect(() => {
    if (!paymentConfig || paymentConfig.payment_provider !== "paypal") return;
    if (document.getElementById("paypal-sdk")) return;
    const script = document.createElement("script");
    script.id = "paypal-sdk";
    script.src = `https://www.paypal.com/sdk/js?client-id=${paymentConfig.paypal_client_id}&vault=true&intent=subscription`;
    script.async = true;
    document.head.appendChild(script);
  }, [paymentConfig]);

  // Render PayPal subscription button
  useEffect(() => {
    if (!paymentConfig || paymentConfig.payment_provider !== "paypal") return;
    if (user.plan !== "free") return;
    const container = document.getElementById("paypal-upgrade-btn");
    if (!container) return;

    const tryRender = () => {
      if (!window.paypal) { setTimeout(tryRender, 300); return; }
      container.innerHTML = "";
      window.paypal.Buttons({
        style: { shape: "rect", color: "blue", layout: "horizontal", label: "subscribe" },
        createSubscription: (_data, actions) =>
          actions.subscription.create({
            plan_id: paymentConfig.paypal_plan_id,
            custom_id: user.email,
          }),
        onApprove: async (data) => {
          try {
            await api("/paypal/capture", {
              method: "POST",
              token,
              body: { subscription_id: data.subscriptionID },
            });
            await fetchUsage();
          } catch (e) {
            alert("PayPal 订阅确认失败：" + e.message);
          }
        },
        onError: (err) => {
          console.error("PayPal error", err);
          alert("PayPal 出现错误，请重试");
        },
      }).render("#paypal-upgrade-btn");
    };
    tryRender();
  }, [paymentConfig, user.plan, user.email, token, fetchUsage]);

  // Form state
  const [productName, setProductName] = useState("");
  const [features, setFeatures] = useState("");
  const [audience, setAudience] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState(["amazon"]);
  const [tone, setTone] = useState("professional");

  // Result state
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("amazon");

  // Fetch usage on mount
  const fetchUsage = useCallback(async () => {
    try {
      const data = await api("/auth/me", { token });
      setUser({ id: data.id, email: data.email, plan: data.plan });
      setUsage(data.usage);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { fetchUsage(); }, [fetchUsage]);

  const togglePlatform = (id) => {
    setSelectedPlatforms(prev =>
      prev.includes(id) ? (prev.length > 1 ? prev.filter(p => p !== id) : prev) : [...prev, id]
    );
  };

  const handleGenerate = async () => {
    setError(""); setLoading(true); setResults(null);
    try {
      const data = await api("/generate", {
        method: "POST", token,
        body: { product_name: productName, features, audience, platforms: selectedPlatforms, tone },
      });
      setResults(data.results);
      setActiveTab(selectedPlatforms[0]);
      setUsage(prev => prev ? { ...prev, remaining: data.remaining, used: prev.limit - data.remaining } : prev);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f0f4f8", fontFamily: font }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ background: darkBg, padding: "16px 0", borderBottom: `3px solid ${blue}` }}>
        <div style={{ maxWidth: "900px", margin: "0 auto", padding: "0 24px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: "20px", fontFamily: monoFont, color: "#fff" }}>
              <span style={{ color: blue }}>◆</span> ListingPilot
            </h1>
          </div>
          <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            {usage && (
              <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                {usage.remaining}/{usage.limit} left today
              </span>
            )}
            {user.plan === "free" ? (
              paymentConfig?.payment_provider === "paypal" ? (
                <div id="paypal-upgrade-btn" style={{ minWidth: "150px" }} />
              ) : (
                <a
                  href={`${paymentConfig?.checkout_url || ""}?checkout[custom][user_email]=${encodeURIComponent(user.email)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: "7px 16px", fontSize: "13px", fontWeight: 600,
                    background: blue, color: "#fff", border: "none", borderRadius: "8px",
                    textDecoration: "none", fontFamily: font,
                  }}
                >Upgrade — $7/mo</a>
              )
            ) : (
              <span style={{ fontSize: "12px", color: "#34d399", fontWeight: 600 }}>✦ Pro</span>
            )}
            <span style={{ fontSize: "12px", color: "#64748b" }}>{user.email}</span>
            <button onClick={onLogout} style={{
              padding: "7px 14px", fontSize: "12px", background: "transparent",
              color: "#64748b", border: "1px solid #334155", borderRadius: "8px",
              cursor: "pointer", fontFamily: font,
            }}>Log out</button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: "900px", margin: "0 auto", padding: "32px 24px" }}>

        {/* Input Card */}
        <div style={{ ...cardStyle, marginBottom: "24px" }}>
          <div style={{ display: "grid", gap: "18px" }}>
            <div>
              <label style={labelBase}>Product Name</label>
              <input style={inputBase} placeholder="e.g. Premium Bamboo Cutting Board Set"
                value={productName} onChange={e => setProductName(e.target.value)} />
            </div>
            <div>
              <label style={labelBase}>Key Features & Selling Points</label>
              <textarea style={{ ...inputBase, minHeight: "90px", resize: "vertical" }}
                placeholder={"e.g.\n• 3-piece set (large, medium, small)\n• 100% organic Moso bamboo\n• Built-in juice grooves"}
                value={features} onChange={e => setFeatures(e.target.value)} />
            </div>
            <div>
              <label style={labelBase}>Target Audience <span style={{ fontWeight: 400, color: "#94a3b8" }}>(optional)</span></label>
              <input style={inputBase} placeholder="e.g. Home cooks, eco-conscious families"
                value={audience} onChange={e => setAudience(e.target.value)} />
            </div>

            {/* Platforms + Tone */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "18px" }}>
              <div>
                <label style={labelBase}>Platforms</label>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {PLATFORMS.map(p => (
                    <button key={p.id} onClick={() => togglePlatform(p.id)}
                      style={{
                        padding: "8px 14px", fontSize: "13px", borderRadius: "8px",
                        border: selectedPlatforms.includes(p.id) ? `1.5px solid ${blue}` : "1.5px solid #e2e8f0",
                        background: selectedPlatforms.includes(p.id) ? "#eff6ff" : "#fff",
                        color: selectedPlatforms.includes(p.id) ? darkBlue : "#64748b",
                        cursor: "pointer", fontWeight: 500, fontFamily: font,
                      }}>{p.icon} {p.label}</button>
                  ))}
                </div>
              </div>
              <div>
                <label style={labelBase}>Tone</label>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {TONES.map(t => (
                    <button key={t.id} onClick={() => setTone(t.id)}
                      style={{
                        padding: "8px 14px", fontSize: "13px", borderRadius: "8px",
                        border: tone === t.id ? `1.5px solid ${blue}` : "1.5px solid #e2e8f0",
                        background: tone === t.id ? "#eff6ff" : "#fff",
                        color: tone === t.id ? darkBlue : "#64748b",
                        cursor: "pointer", fontWeight: 500, fontFamily: font,
                      }}>{t.label}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div style={{
                padding: "10px 14px", borderRadius: "8px", fontSize: "13px",
                background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca",
              }}>{error}</div>
            )}

            {/* Generate */}
            <button onClick={handleGenerate}
              disabled={loading || !productName.trim() || !features.trim()}
              style={{
                ...btnPrimary,
                opacity: (loading || !productName.trim() || !features.trim()) ? 0.6 : 1,
                cursor: (loading || !productName.trim() || !features.trim()) ? "not-allowed" : "pointer",
              }}>
              {loading
                ? `⟳ Generating for ${selectedPlatforms.length} platform${selectedPlatforms.length > 1 ? "s" : ""}...`
                : `Generate Listings → ${selectedPlatforms.length} platform${selectedPlatforms.length > 1 ? "s" : ""}`}
            </button>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div style={{ ...cardStyle, animation: "fadeIn 0.4s ease" }}>
            {/* Tabs */}
            <div style={{ display: "flex", gap: "4px", marginBottom: "24px", borderBottom: "2px solid #f1f5f9" }}>
              {results.map(r => {
                const p = PLATFORMS.find(x => x.id === r.platform);
                return (
                  <button key={r.platform} onClick={() => setActiveTab(r.platform)}
                    style={{
                      padding: "10px 20px", fontSize: "14px",
                      fontWeight: activeTab === r.platform ? 700 : 500,
                      color: activeTab === r.platform ? darkBlue : "#64748b",
                      background: "transparent", border: "none",
                      borderBottom: activeTab === r.platform ? `2px solid ${blue}` : "2px solid transparent",
                      cursor: "pointer", fontFamily: font, marginBottom: "-2px",
                    }}>{p?.icon} {p?.label || r.platform}</button>
                );
              })}
            </div>

            {/* Active result */}
            {results.map(r => (
              r.platform === activeTab ? <ResultPanel key={r.platform} data={r} /> : null
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
        ::placeholder { color: #94a3b8; }
        * { box-sizing: border-box; }
        input:focus, textarea:focus { border-color: ${blue} !important; }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root App — handles auth state
// ---------------------------------------------------------------------------
export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("lp_token") || "");
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("lp_user") || "null"); } catch { return null; }
  });

  const handleLogin = (newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem("lp_token", newToken);
    localStorage.setItem("lp_user", JSON.stringify(newUser));
  };

  const handleLogout = () => {
    setToken("");
    setUser(null);
    localStorage.removeItem("lp_token");
    localStorage.removeItem("lp_user");
  };

  if (!token || !user) {
    return <AuthScreen onLogin={handleLogin} />;
  }

  return <MainApp token={token} user={user} onLogout={handleLogout} />;
}
