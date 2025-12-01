const industryOptions = [
  "Technology",
  "Healthcare",
  "Finance",
  "Retail",
  "Manufacturing",
  "Education",
];

const professionOptions = [
  "Analyst",
  "Engineer",
  "Founder",
  "Marketer",
  "Operations",
  "Researcher",
  "Other",
];

const tabs = document.querySelectorAll(".tab");
const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const loginMessage = document.getElementById("loginMessage");
const signupMessage = document.getElementById("signupMessage");

const signupIndustry = document.getElementById("signupIndustry");
const signupProfession = document.getElementById("signupProfession");

function populateSelect(select, options) {
  select.innerHTML = "";
  const fragment = document.createDocumentFragment();
  const placeholder = document.createElement("option");
  placeholder.textContent = "Select one";
  placeholder.value = "";
  placeholder.disabled = true;
  placeholder.selected = true;
  fragment.appendChild(placeholder);

  options.forEach((option) => {
    const el = document.createElement("option");
    el.value = option;
    el.textContent = option;
    fragment.appendChild(el);
  });

  select.appendChild(fragment);
}

populateSelect(signupIndustry, industryOptions);
populateSelect(signupProfession, professionOptions);

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((btn) => btn.classList.remove("active"));
    tab.classList.add("active");

    if (tab.dataset.target === "login") {
      loginForm.classList.remove("hidden");
      signupForm.classList.add("hidden");
    } else {
      signupForm.classList.remove("hidden");
      loginForm.classList.add("hidden");
    }

    clearMessage(loginMessage);
    clearMessage(signupMessage);
  });
});

function setMessage(element, type, message) {
  element.textContent = message;
  element.classList.remove("error", "success");
  if (type) {
    element.classList.add(type);
  }
}

function clearMessage(element) {
  element.textContent = "";
  element.classList.remove("error", "success");
}

async function submitForm(url, data, messageElement) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    const responseBody = await response.json();
    if (!response.ok) {
      let detailMessage = "Request failed.";
      if (typeof responseBody.detail === "string") {
        detailMessage = responseBody.detail;
      } else if (Array.isArray(responseBody.detail)) {
        detailMessage = responseBody.detail.map((entry) => entry.msg).join(" ");
      }
      throw new Error(detailMessage);
    }

    setMessage(messageElement, "success", responseBody.message || "Success.");
    return responseBody;
  } catch (error) {
    setMessage(messageElement, "error", error.message);
    return null;
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(loginMessage);

  const data = {
    username: event.target.username.value.trim(),
    password: event.target.password.value,
  };

  const result = await submitForm("/api/login", data, loginMessage);
  if (result?.redirect_to) {
    setTimeout(() => {
      window.location.href = result.redirect_to;
    }, 600);
  }
});

signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(signupMessage);

  const formData = new FormData(event.target);
  const data = Object.fromEntries(formData.entries());

  if (!data.credit_card) {
    delete data.credit_card;
  }

  const result = await submitForm("/api/signup", data, signupMessage);
  if (result?.user_id) {
    event.target.reset();
    populateSelect(signupIndustry, industryOptions);
    populateSelect(signupProfession, professionOptions);
  }
});

