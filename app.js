const state = {
  token: null,
  currentUser: null,
  dashboard: null,
  products: [],
  orders: [],
  commissions: [],
  complaints: [],
  news: [],
  resellers: [],
};

const menuConfig = {
  reseller: ["dashboard", "produk", "order", "komisi", "komplain", "news"],
  admin: ["dashboard", "reseller", "produk", "order", "komisi", "komplain", "news"],
};

const menuLabel = {
  dashboard: "Dashboard",
  produk: "Produk",
  order: "Order",
  komisi: "Komisi",
  komplain: "Komplain",
  news: "News",
  reseller: "Reseller",
};

const authSection = document.getElementById("authSection");
const appSection = document.getElementById("appSection");
const menuEl = document.getElementById("menu");
const viewEl = document.getElementById("view");
const sessionBadge = document.getElementById("sessionBadge");

const currency = new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 });

function formatRupiah(value) {
  return currency.format(value || 0);
}

function formatDate(isoText) {
  return new Date(isoText).toLocaleString("id-ID");
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const res = await fetch(path, { ...options, headers });
  const payload = await res.json();

  if (!res.ok) {
    throw new Error(payload.error || "Request gagal.");
  }

  return payload;
}

function setSession(user, token) {
  state.currentUser = user;
  state.token = token || null;

  if (!user) {
    authSection.classList.remove("hidden");
    appSection.classList.add("hidden");
    sessionBadge.textContent = "Belum login";
    return;
  }

  authSection.classList.add("hidden");
  appSection.classList.remove("hidden");
  sessionBadge.textContent = `${user.name} (${user.role})`;
  buildMenu(user.role);
  renderView("dashboard");
}

function buildMenu(role) {
  menuEl.innerHTML = "";
  menuConfig[role].forEach((item, index) => {
    const btn = document.createElement("button");
    btn.dataset.target = item;
    btn.textContent = menuLabel[item];
    if (index === 0) btn.classList.add("active");

    btn.addEventListener("click", () => {
      document.querySelectorAll("#menu button").forEach((node) => node.classList.remove("active"));
      btn.classList.add("active");
      renderView(item);
    });

    menuEl.appendChild(btn);
  });
}

async function loadDashboard() {
  state.dashboard = await api("/api/dashboard");
}

async function loadProducts() {
  state.products = await api("/api/products");
}

async function loadOrders() {
  state.orders = await api("/api/orders");
}

async function loadCommissions() {
  state.commissions = await api("/api/commissions");
}

async function loadComplaints() {
  state.complaints = await api("/api/complaints");
}

async function loadNews() {
  state.news = await api("/api/news");
}

async function loadResellers() {
  if (state.currentUser?.role === "admin") {
    state.resellers = await api("/api/admin/resellers");
  }
}

function renderDashboard() {
  if (state.currentUser.role === "admin") {
    return `
      <section class="panel">
        <h2>Dashboard Admin</h2>
        <div class="stats">
          <div class="stat"><strong>${state.dashboard.resellerTotal}</strong><div>Total Reseller</div></div>
          <div class="stat"><strong>${state.dashboard.pendingApproval}</strong><div>Pending Approval</div></div>
          <div class="stat"><strong>${state.dashboard.orderTotal}</strong><div>Total Order</div></div>
          <div class="stat"><strong>${state.dashboard.complaintTotal}</strong><div>Total Komplain</div></div>
        </div>
      </section>
    `;
  }

  return `
    <section class="panel">
      <h2>Dashboard Reseller</h2>
      <div class="stats">
        <div class="stat"><strong>${state.dashboard.productTotal}</strong><div>Produk Aktif</div></div>
        <div class="stat"><strong>${state.dashboard.myOrderTotal}</strong><div>Total Order</div></div>
        <div class="stat"><strong>${formatRupiah(state.dashboard.myCommissionTotal)}</strong><div>Total Komisi</div></div>
        <div class="stat"><strong>${new Date().toLocaleString("id-ID")}</strong><div>Waktu Akses</div></div>
      </div>
    </section>
  `;
}

function renderProducts() {
  const rows = state.products
    .map(
      (p) => `<tr>
      <td>${p.name}</td>
      <td class="${p.stock < 25 ? "text-danger" : "text-success"}">${p.stock}</td>
      <td>${formatRupiah(p.basePrice)}</td>
      <td>${formatRupiah(p.resellerPrice)}</td>
      <td>${p.commissionRate}%</td>
    </tr>`,
    )
    .join("");

  const adminForm =
    state.currentUser.role === "admin"
      ? `<form id="newProductForm" class="card">
        <h3>Tambah Produk</h3>
        <label>Nama Produk <input id="newProductName" required /></label>
        <label>Stok Awal <input id="newProductStock" type="number" min="0" required /></label>
        <label>Harga Normal <input id="newProductBase" type="number" min="0" required /></label>
        <label>Harga Reseller <input id="newProductReseller" type="number" min="0" required /></label>
        <label>Komisi (%) <input id="newProductCommission" type="number" min="0" max="100" required /></label>
        <button type="submit">Simpan Produk</button>
      </form>`
      : "";

  return `
    <section class="panel">
      <h2>Monitoring Produk, Stok, dan Harga</h2>
      ${adminForm}
      <div class="table-wrap">
        <table>
          <thead><tr><th>Produk</th><th>Stok</th><th>Harga Normal</th><th>Harga Reseller</th><th>Komisi</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='5'>Belum ada produk</td></tr>"}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderOrders() {
  const options = state.products.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
  const rows = state.orders
    .map(
      (o) => `<tr><td>${o.id}</td><td>${o.resellerName}</td><td>${o.productName}</td><td>${o.type}</td><td>${o.qty}</td><td>${formatRupiah(o.total)}</td><td>${formatRupiah(o.commissionAmount)}</td><td>${formatDate(o.createdAt)}</td></tr>`,
    )
    .join("");

  const orderForm =
    state.currentUser.role === "reseller"
      ? `<form id="orderForm" class="card">
        <label>Produk <select id="orderProduct" required>${options}</select></label>
        <label>Tipe Order <select id="orderType"><option value="satuan">Satuan</option><option value="borongan">Borongan</option></select></label>
        <label>Qty <input id="orderQty" type="number" min="1" required /></label>
        <button type="submit">Buat Order</button>
      </form>`
      : "<p class='small'>Admin memonitor seluruh order reseller.</p>";

  return `
    <section class="panel">
      <h2>Sistem Order</h2>
      ${orderForm}
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Reseller</th><th>Produk</th><th>Tipe</th><th>Qty</th><th>Total</th><th>Komisi</th><th>Waktu</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='8'>Belum ada order</td></tr>"}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderCommissions() {
  const total = state.commissions.reduce((sum, c) => sum + c.commissionAmount, 0);
  const rows = state.commissions
    .map(
      (c) => `<tr><td>${c.orderId}</td><td>${c.resellerName}</td><td>${c.productName}</td><td>${formatRupiah(c.total)}</td><td>${formatRupiah(c.commissionAmount)}</td><td>${formatDate(c.createdAt)}</td></tr>`,
    )
    .join("");

  return `
    <section class="panel">
      <h2>Sistem Komisi Otomatis</h2>
      <p>Total komisi: <strong>${formatRupiah(total)}</strong></p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Order ID</th><th>Reseller</th><th>Produk</th><th>Nilai</th><th>Komisi</th><th>Waktu</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='6'>Belum ada komisi</td></tr>"}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderComplaints() {
  const rows = state.complaints
    .map((c) => `<tr><td>${c.id}</td><td>${c.resellerName}</td><td>${c.message}</td><td>${c.status}</td><td>${formatDate(c.createdAt)}</td></tr>`)
    .join("");

  const form =
    state.currentUser.role === "reseller"
      ? `<form id="complaintForm" class="card">
        <label>Keluhan / Feedback
          <textarea id="complaintMessage" rows="3" required></textarea>
        </label>
        <button type="submit">Kirim</button>
      </form>`
      : "<p class='small'>Admin memonitor komplain reseller secara terpusat.</p>";

  return `
    <section class="panel">
      <h2>Komplain & Feedback</h2>
      ${form}
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Reseller</th><th>Pesan</th><th>Status</th><th>Waktu</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='5'>Belum ada komplain</td></tr>"}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderNews() {
  const rows = state.news
    .map(
      (n) => `<article class="card"><h3>${n.title}</h3><p>${n.content}</p><p class="small">Oleh ${n.author} • ${formatDate(n.createdAt)}</p></article>`,
    )
    .join("");

  const adminForm =
    state.currentUser.role === "admin"
      ? `<form id="newsForm" class="card">
        <label>Judul <input id="newsTitle" required /></label>
        <label>Konten <textarea id="newsContent" rows="3" required></textarea></label>
        <button type="submit">Posting Update</button>
      </form>`
      : "";

  return `
    <section class="panel">
      <h2>News / Update Produk</h2>
      ${adminForm}
      <div class="grid-2">${rows || "<p>Belum ada update.</p>"}</div>
    </section>
  `;
}

function renderResellers() {
  const rows = state.resellers
    .map(
      (r) => `<tr>
      <td>${r.name}</td>
      <td>${r.email}</td>
      <td>${r.resellerType}</td>
      <td>${r.status}</td>
      <td>${r.status === "pending" ? `<button data-action="approve" data-id="${r.id}">Approve</button>` : "-"}</td>
    </tr>`,
    )
    .join("");

  return `
    <section class="panel">
      <h2>Panel Admin - Manajemen Reseller</h2>
      <p class="small">Pendaftaran masuk dari form + WhatsApp, kemudian disetujui admin.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Nama</th><th>Email</th><th>Tipe</th><th>Status</th><th>Aksi</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='5'>Belum ada reseller.</td></tr>"}</tbody>
        </table>
      </div>
    </section>
  `;
}

async function renderView(target) {
  if (!state.currentUser) {
    return;
  }

  try {
    if (target === "dashboard") {
      await loadDashboard();
      viewEl.innerHTML = renderDashboard();
    }

    if (target === "produk") {
      await loadProducts();
      viewEl.innerHTML = renderProducts();
    }

    if (target === "order") {
      await Promise.all([loadProducts(), loadOrders()]);
      viewEl.innerHTML = renderOrders();
    }

    if (target === "komisi") {
      await loadCommissions();
      viewEl.innerHTML = renderCommissions();
    }

    if (target === "komplain") {
      await loadComplaints();
      viewEl.innerHTML = renderComplaints();
    }

    if (target === "news") {
      await loadNews();
      viewEl.innerHTML = renderNews();
    }

    if (target === "reseller") {
      await loadResellers();
      viewEl.innerHTML = renderResellers();
    }

    bindDynamicHandlers(target);
  } catch (error) {
    viewEl.innerHTML = `<section class="panel"><p class="text-danger">${error.message}</p></section>`;
  }
}

function bindDynamicHandlers(target) {
  if (target === "order") {
    document.getElementById("orderForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/orders", {
          method: "POST",
          body: JSON.stringify({
            productId: Number(document.getElementById("orderProduct").value),
            type: document.getElementById("orderType").value,
            qty: Number(document.getElementById("orderQty").value),
          }),
        });
        await renderView("order");
        alert("Order berhasil dibuat.");
      } catch (error) {
        alert(error.message);
      }
    });
  }

  if (target === "komplain") {
    document.getElementById("complaintForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/complaints", {
          method: "POST",
          body: JSON.stringify({ message: document.getElementById("complaintMessage").value.trim() }),
        });
        await renderView("komplain");
      } catch (error) {
        alert(error.message);
      }
    });
  }

  if (target === "news") {
    document.getElementById("newsForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/news", {
          method: "POST",
          body: JSON.stringify({
            title: document.getElementById("newsTitle").value.trim(),
            content: document.getElementById("newsContent").value.trim(),
          }),
        });
        await renderView("news");
      } catch (error) {
        alert(error.message);
      }
    });
  }

  if (target === "reseller") {
    document.querySelectorAll("button[data-action='approve']").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await api(`/api/admin/resellers/${button.dataset.id}/approve`, { method: "POST" });
          await renderView("reseller");
        } catch (error) {
          alert(error.message);
        }
      });
    });
  }

  if (target === "produk") {
    document.getElementById("newProductForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/products", {
          method: "POST",
          body: JSON.stringify({
            name: document.getElementById("newProductName").value.trim(),
            stock: Number(document.getElementById("newProductStock").value),
            basePrice: Number(document.getElementById("newProductBase").value),
            resellerPrice: Number(document.getElementById("newProductReseller").value),
            commissionRate: Number(document.getElementById("newProductCommission").value),
          }),
        });
        await renderView("produk");
      } catch (error) {
        alert(error.message);
      }
    });
  }
}

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const result = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("loginEmail").value.trim().toLowerCase(),
        password: document.getElementById("loginPassword").value,
        role: document.getElementById("loginRole").value,
      }),
    });
    setSession(result.user, result.token);
  } catch (error) {
    alert(error.message);
  }
});

document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/resellers/register", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("registerName").value.trim(),
        resellerType: document.getElementById("registerType").value,
        email: document.getElementById("registerEmail").value.trim().toLowerCase(),
      }),
    });
    alert("Pendaftaran dikirim. Silakan lanjutkan verifikasi lewat WhatsApp.");
    e.target.reset();
  } catch (error) {
    alert(error.message);
  }
});

document.getElementById("logoutBtn").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (_error) {
    // no-op
  }
  setSession(null, null);
});

setSession(null, null);
