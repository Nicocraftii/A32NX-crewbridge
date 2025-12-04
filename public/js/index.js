let darkmode = localStorage.getItem("darkmode");

if (darkmode === "enabled") {
    document.body.classList.add("darkmode");
} else {
    document.body.classList.remove("darkmode");
}

document.getElementById("modebtn").addEventListener("click", () => {
    darkmode = localStorage.getItem("darkmode");

    if (darkmode !== "enabled") {
        document.body.classList.add("darkmode");
        localStorage.setItem("darkmode", "enabled");
    } else {
        document.body.classList.remove("darkmode");
        localStorage.setItem("darkmode", "disabled");
    }
});

const settingsBtn = document.querySelector(".nav.btn.b5");
const settingsPanel = document.getElementById("settings");
const overlay = document.getElementById("overlay");

settingsBtn.addEventListener("click", () => {
    if (settingsPanel.style.display === "grid") {
        settingsPanel.style.display = "none";
        settingsPanel.style.opacity = "0";
        settingsPanel.style.zIndex = "-10";
        overlay.style.display = "none";
        overlay.style.pointerEvents = "none";
        overlay.style.opacity = "0";

        document.getElementById("container").style.filter = "none";
    } else {
        settingsPanel.style.display = "grid";
        settingsPanel.style.opacity = "1";
        settingsPanel.style.zIndex = "10";
        overlay.style.display = "block";
        overlay.style.pointerEvents = "auto";
        overlay.style.opacity = "1";

        document.getElementById("container").style.filter = "blur(5px)";
    }
});

document.getElementById("saveSettings").addEventListener("click", () => {
    settingsPanel.style.display = "none";
    settingsPanel.style.opacity = "0";
    overlay.style.display = "none";
    overlay.style.pointerEvents = "none";
    overlay.style.opacity = "0";

    document.getElementById("container").style.filter = "none";
});

const dashbtn = document.getElementById("dashbtn");
const slider = dashbtn.querySelector(".slider");

let active = "Client";

dashbtn.addEventListener("click", (e) => {
    const rect = dashbtn.getBoundingClientRect();
    const clickX = e.clientX - rect.left;

    if (clickX < rect.width / 2 && active !== "Client") {
        slider.style.transform = "translateX(0%)";
        active = "Client";
        document.querySelector("#host").style.display = "none";
        document.querySelector("#client").style.display = "grid";
        dashbtn.classList.add("active");
    } else if (clickX >= rect.width / 2 && active !== "Server") {
        slider.style.transform = "translateX(100%)";
        active = "Server";
        document.querySelector("#host").style.display = "grid";
        document.querySelector("#client").style.display = "none";
        dashbtn.classList.remove("active");
    }
});

document.querySelectorAll(".localIp").forEach((element) => {
    if (element.classList.contains("blurrable")) {
        element.addEventListener("click", () => {
            if (element.style.filter === "none") {
                element.style.filter = "blur(0.3rem)";
            } else {
                element.style.filter = "none";
            }
        });
    }
});

function updateConnectionStatus() {
    fetch("/status")
        .then((res) => res.json())
        .then((data) => {
            const ipElements = document.querySelectorAll(".localIp");
            ipElements.forEach((el) => (el.textContent = data.ip));

            if (data.ip === "Connection error") {
                toast(
                    "Connection Error",
                    "Missing internet connection.",
                    0,
                    5200
                );
                document.getElementById("dashboard").style.opacity = "0";
                ipElements.forEach((element) => {
                    element.classList.add("no-blur");
                    element.classList.remove("blurrable");
                });
            } else {
                if (document.getElementById("dashboard").style.opacity == "0") {
                    ipElements.forEach((element) => {
                        element.classList.remove("no-blur");
                        element.classList.add("blurrable");
                    });
                    toast("Info", "Welcome to A32NX Crewbridge!", 2, 4000);
                    document.getElementById("dashboard").style.opacity = "1";
                }
            }
        })
        .catch((err) => {
            console.error("Status check failed:", err);
            toast("Connection Error", "Could not reach the backend.", 0, 4500);
        });
}

const TOAST_ICONS = {
    error: `
        <svg viewBox="0 0 24 24" fill="#ff3b30">
            <circle cx="12" cy="12" r="11" stroke="#ff3b30" stroke-width="2" fill="none"/>
            <line x1="8" y1="8" x2="16" y2="16" stroke="#ff3b30" stroke-width="2" stroke-linecap="round"/>
            <line x1="16" y1="8" x2="8" y2="16" stroke="#ff3b30" stroke-width="2" stroke-linecap="round"/>
        </svg>
    `,
    warn: `
        <svg viewBox="0 0 24 24" fill="#ffcc00">
            <polygon points="12,2 2,22 22,22" stroke="#ffcc00" stroke-width="2" fill="none"/>
            <line x1="12" y1="10" x2="12" y2="14" stroke="#ffcc00" stroke-width="2" stroke-linecap="round"/>
            <circle cx="12" cy="17" r="1" stroke="#ffcc00" fill="#ffcc00"/>
        </svg>
    `,
    info: `
        <svg viewBox="0 0 24 24" fill="#007aff">
            <circle cx="12" cy="12" r="11" stroke="#007aff" stroke-width="2" fill="none"/>
            <line x1="12" y1="10" x2="12" y2="17" stroke="#007aff" stroke-width="2" stroke-linecap="round"/>
            <circle cx="12" cy="6" r="0.75" stroke="#007aff" fill="#007aff"/>
        </svg>
    `,
};

function toast(title, text, level = 2, time = 3000) {
    const toastEl = document.getElementById("toast");
    const titleEl = toastEl.querySelector("h6");
    const textEl = toastEl.querySelector("a");
    const iconEl = toastEl.querySelector(".icon");

    titleEl.textContent = title;
    textEl.textContent = text;

    toastEl.classList.remove("terr", "twarn", "tinfo");

    if (level === 0) {
        toastEl.classList.add("terr");
        iconEl.innerHTML = TOAST_ICONS.error;
    } else if (level === 1) {
        toastEl.classList.add("twarn");
        iconEl.innerHTML = TOAST_ICONS.warn;
    } else {
        toastEl.classList.add("tinfo");
        iconEl.innerHTML = TOAST_ICONS.info;
    }

    toastEl.classList.add("show");
    if (toastEl.hideTimeout) clearTimeout(toastEl.hideTimeout);

    toastEl.hideTimeout = setTimeout(() => {
        toastEl.classList.remove("show");
    }, time);
}

let port = localStorage.getItem("port") || "0000";
document.getElementById("list-port").textContent = port;

document.getElementById("host-code-input").addEventListener("input", (el) => {
    const inputEl = document.getElementById("host-code-input");
    const preserveSelection = (el, oldVal, newVal, oldStart, oldEnd) => {
        const prefixOld = oldVal.slice(0, oldStart);
        const prefixNew = newVal.slice(0, prefixOld.length);
        const newStart = Math.min(newVal.length, prefixNew.length);
        el.setSelectionRange(newStart, newStart);
    };

    inputEl.addEventListener("input", (e) => {
        const el = e.target;
        const oldVal = el.value;
        const oldStart = el.selectionStart;
        const oldEnd = el.selectionEnd;

        const newVal = oldVal.toUpperCase().replace(/[^A-Z0-9]/g, "");

        if (newVal !== oldVal) {
            el.value = newVal;
            preserveSelection(el, oldVal, newVal, oldStart, oldEnd);
        }
    });
});


function updateClientInfo() {
    document.querySelectorAll('.client-mfs-version').forEach(el => {
        el.textContent = localStorage.getItem('mfsVersion');
    });
}

setInterval(updateClientInfo, 3000);



const ipInput = document.getElementById("host-ip-input");

ipInput.addEventListener("input", (e) => {
    const el = e.target;
    const oldVal = el.value;
    const oldPos = el.selectionStart;

    const newVal = oldVal.replace(/[^0-9.]/g, "");

    if (newVal !== oldVal) {
        const prefixOld = oldVal.slice(0, oldPos);
        const allowedBefore = prefixOld.replace(/[^0-9.]/g, "").length;
        const newPos = Math.min(allowedBefore, newVal.length);

        el.value = newVal;
        el.setSelectionRange(newPos, newPos);
    }
});

// ... (keep all the existing code until the getstarted function)

function getstarted() {
    const Panel = document.getElementById("getstarted");
    const overlay = document.getElementById("overlay");
    const container = document.getElementById("container");

    if (Panel.style.opacity === "1") {
        Panel.style.opacity = "0";
        Panel.style.zIndex = "-10";
        overlay.style.display = "none";
        overlay.style.pointerEvents = "none";
        overlay.style.opacity = "0";
        container.style.filter = "none";
        setTimeout(() => {
            Panel.style.display = "none";
            resetPage3(); // Reset when closing
        }, 500);
    } else {
        Panel.style.display = "flex";
        setTimeout(() => {
            Panel.style.opacity = "1";
            Panel.style.zIndex = "11";
            overlay.style.display = "block";
            overlay.style.pointerEvents = "auto";
            overlay.style.opacity = "1";
            container.style.filter = "blur(5px)";
            showPage(0); // Show first page
        }, 10);
    }
}

setInterval(updateConnectionStatus, 5000);

document.addEventListener("DOMContentLoaded", () => {
    updateConnectionStatus();
    updateClientInfo();

    // Check if wizard should show (use showWizard preference)
    const showWizard = localStorage.getItem("showWizard") !== "false"; // Default to true if not set

    // Only show wizard if showWizard is true
    if (showWizard) {
        // Show wizard after a short delay
        setTimeout(() => {
            getstarted();
        }, 50);
    }
});

// Get Started Wizard Logic
const wizardPages = ["page1", "page2", "page3"];
let currentPage = 0;
let isAnalyzing = false;
let lastCheckResult = null;

// Load saved data from localStorage
let wizardData = {
    mfsVersion: localStorage.getItem("mfsVersion") || "",
    communityPath: localStorage.getItem("communityPath") || "",
    showWizard: localStorage.getItem("showWizard") !== "false", // Default to true
};

function resetPage3() {
    const analysisContent = document.getElementById("analysisContent");
    const resultContent = document.getElementById("resultContent");
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");
    const analysisTitle = document.getElementById("analysisTitle");
    const analysisText = document.getElementById("analysisText");
    const showAgainCheckbox = document.getElementById("showAgainCheckbox");

    if (analysisContent) analysisContent.classList.remove("hidden");
    if (resultContent) resultContent.classList.add("hidden");
    if (progressFill) progressFill.style.width = "0%";
    if (progressText) progressText.textContent = "0%";
    if (analysisTitle)
        analysisTitle.textContent = "Analyzing Community Folder...";
    if (analysisText)
        analysisText.textContent = "Please wait while we check your setup.";
    if (showAgainCheckbox) showAgainCheckbox.checked = !wizardData.showWizard;

    isAnalyzing = false;
    lastCheckResult = null;
}

function showPage(pageIndex) {
    // Hide all pages
    wizardPages.forEach((pageId, index) => {
        const page = document.getElementById(pageId);
        if (page) {
            page.classList.remove("active");
        }
        const indicator = document.querySelector(
            `.step-indicator[data-step="${index + 1}"]`
        );
        if (indicator) {
            indicator.classList.remove("active");
        }
    });

    // Show current page
    const currentPageElement = document.getElementById(wizardPages[pageIndex]);
    if (currentPageElement) {
        currentPageElement.classList.add("active");
    }

    const currentIndicator = document.querySelector(
        `.step-indicator[data-step="${pageIndex + 1}"]`
    );
    if (currentIndicator) {
        currentIndicator.classList.add("active");
    }

    // Update button visibility

    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const finishBtn = document.getElementById("finishBtn");

    if (prevBtn) prevBtn.style.display = pageIndex === 0 ? "none" : "block";
    if (nextBtn)
        nextBtn.style.display =
            pageIndex === wizardPages.length - 1 ? "none" : "block";
    if (finishBtn)
        finishBtn.style.display =
            pageIndex === wizardPages.length - 1 ? "none" : "none";


    // Reset page 3 when leaving it
    if (pageIndex !== 2 && currentPage === 2) {
        resetPage3();
    }

    // Start analysis when going to page 3
    if (pageIndex === 2 && !isAnalyzing) {
        analyzeCommunityFolder();
    }

    currentPage = pageIndex;
}

function saveToLocalStorage() {
    localStorage.setItem("mfsVersion", wizardData.mfsVersion);
    localStorage.setItem("communityPath", wizardData.communityPath);
    localStorage.setItem("showWizard", wizardData.showWizard);
}

async function analyzeCommunityFolder() {
    if (isAnalyzing) return;

    isAnalyzing = true;
    const analysisTitle = document.getElementById("analysisTitle");
    const analysisText = document.getElementById("analysisText");
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");

    if (!analysisTitle || !progressFill) {
        isAnalyzing = false;
        return;
    }

    // Reset and show analysis state
    resetPage3();

    progressFill.style.width = "20%";
    progressText.textContent = "20%";

    analysisTitle.textContent = "Checking folder path...";
    analysisText.textContent = "Validating the community folder...";

    try {
        // First check if the folder exists and is accessible
        const response = await fetch("/check-community-folder", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                path: wizardData.communityPath,
            }),
        });

        progressFill.style.width = "50%";
        progressText.textContent = "50%";

        const data = await response.json();
        lastCheckResult = data;

        if (!data.success) {
            // Folder doesn't exist or other error
            isAnalyzing = false;
            showResult(
                false,
                "Folder Error",
                data.error ||
                    "There was an error checking the folder. Please verify the path."
            );
            return;
        }

        progressFill.style.width = "70%";
        progressText.textContent = "70%";

        if (data.hasModule) {
            analysisTitle.textContent = "Module found!";
            analysisText.textContent =
                "The mobiflight-event-module is already installed.";

            progressFill.style.width = "100%";
            progressText.textContent = "100%";

            setTimeout(() => {
                isAnalyzing = false;
                showResult(
                    true,
                    "Already Installed!",
                    "The mobiflight-event-module is already in your community folder. You're ready to use A32NX Crewbridge."
                );
            }, 1000);
        } else {
            analysisTitle.textContent = "Installing module...";
            analysisText.textContent = "Running the Python installer script...";

            progressFill.style.width = "85%";
            progressText.textContent = "85%";

            // Execute Python script
            const installResponse = await fetch("/run-installer", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    path: wizardData.communityPath,
                }),
            });

            const installResult = await installResponse.json();

            progressFill.style.width = "100%";
            progressText.textContent = "100%";

            if (installResult.success) {
                setTimeout(() => {
                    isAnalyzing = false;
                    showResult(
                        true,
                        "Installation Complete!",
                        installResult.message ||
                            "All required modules have been installed successfully."
                    );
                }, 1000);
            } else {
                setTimeout(() => {
                    isAnalyzing = false;

                    let errorMessage =
                        "There was an error running the installer. ";
                    if (installResult.error) {
                        errorMessage += installResult.error;
                    }
                    if (installResult.suggestion) {
                        errorMessage += ` Suggestion: ${installResult.suggestion}`;
                    }

                    // Log to console for debugging
                    console.error("Installer failed:");

                    showResult(false, "Installation Failed");
                }, 1000);
            }
        }
    } catch (error) {
        console.error("Analysis failed:", error);
        isAnalyzing = false;

        let errorMessage = "Could not analyze the community folder. ";
        if (error.message.includes("Failed to fetch")) {
            errorMessage +=
                "Could not connect to the server. Make sure the server is running.";
        } else if (error.message.includes("NetworkError")) {
            errorMessage += "Network error. Please check your connection.";
        } else {
            errorMessage += `Error: ${error.message}`;
        }

        setTimeout(() => {
            showResult(false, "Analysis Failed", errorMessage);
        }, 500);
    }
}

function showResult(success, title, message) {
    const analysisContent = document.getElementById("analysisContent");
    const resultContent = document.getElementById("resultContent");
    const resultTitle = document.getElementById("resultTitle");
    const resultText = document.getElementById("resultText");
    const resultIcon = document.getElementById("resultIcon");
    const showAgainCheckbox = document.getElementById("showAgainCheckbox");

    if (!analysisContent || !resultContent) return;

    // Set result content
    resultTitle.textContent = title;
    resultText.textContent = message;

    // Set checkbox state
    if (showAgainCheckbox) {
        showAgainCheckbox.checked = !wizardData.showWizard;
    }

    // Set icon based on success
    if (success) {
        resultIcon.innerHTML = `
      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill="var(--green)" stroke="var(--green)"/>
    `;
    } else {
        resultIcon.innerHTML = `
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="var(--red)" stroke="var(--red)"/>
    `;
    }

    // Show result, hide analysis
    analysisContent.classList.add("hidden");
    resultContent.classList.remove("hidden");
    const finishBtn = document.getElementById("finishBtn");
    const nextBtn = document.getElementById("nextBtn");

    updateClientInfo();

    if (finishBtn) finishBtn.style.display = "block";
    if (nextBtn) nextBtn.style.display = "none";
}

// Event Listeners for Wizard
document.addEventListener("DOMContentLoaded", () => {
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const finishBtn = document.getElementById("finishBtn");
    const mfsVersionSelect = document.getElementById("mfsVersion");
    const communityPathInput = document.getElementById("communityPath");
    const showAgainCheckbox = document.getElementById("showAgainCheckbox");

    // Check if wizard elements exist
    const wizardExists = document.getElementById("getstarted") !== null;

    if (!wizardExists) {
        console.log("Wizard not found in DOM");
        return;
    }

    // Load saved values
    if (mfsVersionSelect && wizardData.mfsVersion) {
        mfsVersionSelect.value = wizardData.mfsVersion;
    }

    if (communityPathInput && wizardData.communityPath) {
        communityPathInput.value = wizardData.communityPath;
    }

    if (showAgainCheckbox) {
        showAgainCheckbox.checked = !wizardData.showWizard;
    }

    // Navigation
    if (nextBtn) {
        nextBtn.addEventListener("click", () => {
            if (currentPage === 1) {
                // Save data from page 2
                wizardData.mfsVersion = mfsVersionSelect.value;
                wizardData.communityPath = communityPathInput.value.trim();
                saveToLocalStorage();

                // Validate before proceeding
                if (!wizardData.mfsVersion) {
                    toast(
                        "Validation Error",
                        "Please select an MSFS version.",
                        0,
                        3000
                    );
                    return;
                }

                if (!wizardData.communityPath) {
                    toast(
                        "Validation Error",
                        "Please specify the community folder path.",
                        0,
                        3000
                    );
                    return;
                }

                // Move to analysis page
                showPage(2);
            } else {
                showPage(currentPage + 1);
            }
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener("click", () => {
            showPage(currentPage - 1);
        });
    }

    if (finishBtn) {
        finishBtn.addEventListener("click", () => {
            // Save show wizard preference
            if (showAgainCheckbox) {
                wizardData.showWizard = !showAgainCheckbox.checked;
                saveToLocalStorage();
            }

            getstarted(); // Close wizard
            toast(
                "Setup Complete",
                "A32NX Crewbridge is ready to use!",
                2,
                4000
            );
        });
    }


    // Save data when inputs change
    if (mfsVersionSelect) {
        mfsVersionSelect.addEventListener("change", () => {
            wizardData.mfsVersion = mfsVersionSelect.value;
            saveToLocalStorage();
        });
    }

    if (communityPathInput) {
        communityPathInput.addEventListener("input", () => {
            wizardData.communityPath = communityPathInput.value;
            saveToLocalStorage();
        });

        communityPathInput.addEventListener("blur", (e) => {
            // Normalize path on blur
            let path = e.target.value.trim();
            // Remove trailing slashes
            path = path.replace(/[\/\\]+$/, "");
            e.target.value = path;
            wizardData.communityPath = path;
            saveToLocalStorage();
        });
    }

    if (showAgainCheckbox) {
        showAgainCheckbox.addEventListener("change", () => {
            wizardData.showWizard = !showAgainCheckbox.checked;
            saveToLocalStorage();
        });
    }
});




document.getElementById("launchWizardBtn").addEventListener("click", () => {
    document.getElementById("settings").style.display = "none";
    getstarted();
});