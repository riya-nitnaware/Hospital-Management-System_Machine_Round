
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("appointment-form");
    const dateInput = document.getElementById("appointment-date");
    const slotsContainer = document.getElementById("time-slots");
    const startTimeInput = document.getElementById("start_time");
    const messageBox = document.getElementById("booking-message");

    // Do nothing on pages without the appointment form.
    if (!form || !dateInput || !slotsContainer || !startTimeInput) {
        return;
    }

    const doctorInput = form.querySelector('[name="doctor_id"]');
    const doctorId = doctorInput?.value || form.dataset.doctorId;

    const csrfInput = form.querySelector('[name="csrf_token"]');
    let requestNumber = 0;

    // Use local date rather than UTC to avoid date mismatches.
    function getToday() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    dateInput.min = getToday();

    function showMessage(message, type = "info") {
        if (!messageBox) {
            console.log(message);
            return;
        }

        messageBox.textContent = message;
        messageBox.className = `booking-message ${type}`;
        messageBox.hidden = false;
    }

    function clearMessage() {
        if (!messageBox) return;

        messageBox.textContent = "";
        messageBox.hidden = true;
        messageBox.className = "booking-message";
    }

    function showSlotMessage(message) {
        slotsContainer.replaceChildren();

        const paragraph = document.createElement("p");
        paragraph.className = "slots-message";
        paragraph.textContent = message;

        slotsContainer.appendChild(paragraph);
    }

    function formatTime(value) {
        // The Flask endpoint returns YYYY-MM-DDTHH:MM.
        const match = String(value).match(/T(\d{2}):(\d{2})/);

        if (!match) return value;

        let hours = Number(match[1]);
        const minutes = match[2];
        const period = hours >= 12 ? "PM" : "AM";

        hours = hours % 12 || 12;

        return `${hours}:${minutes} ${period}`;
    }

    async function loadAvailableSlots() {
        const currentRequest = ++requestNumber;

        startTimeInput.value = "";
        clearMessage();

        if (!doctorId) {
            showSlotMessage("Doctor information is missing.");
            return;
        }

        const selectedDate = dateInput.value;

        if (!selectedDate) {
            showSlotMessage("Please select a date first.");
            return;
        }

        if (selectedDate < getToday()) {
            showSlotMessage("Past dates cannot be booked.");
            return;
        }

        showSlotMessage("Loading available time slots...");

        try {
            const params = new URLSearchParams({
                doctor_id: doctorId,
                date: selectedDate
            });

            const response = await fetch(
                `/appointments/slots?${params.toString()}`,
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    credentials: "same-origin"
                }
            );

            const data = await response.json();

            // Ignore older requests if the user changed the date quickly.
            if (currentRequest !== requestNumber) return;

            if (!response.ok || !data.success) {
                throw new Error(
                    data.message || "Unable to load available slots."
                );
            }

            slotsContainer.replaceChildren();

            if (!Array.isArray(data.slots) || data.slots.length === 0) {
                showSlotMessage(
                    data.message ||
                    "No available slots for this date. Please choose another date."
                );
                return;
            }

            data.slots.forEach((slot) => {
                const button = document.createElement("button");

                button.type = "button";
                button.className = "time-slot";
                button.textContent = formatTime(slot);
                button.setAttribute("aria-pressed", "false");

                button.addEventListener("click", () => {
                    slotsContainer
                        .querySelectorAll(".time-slot")
                        .forEach((item) => {
                            item.classList.remove("selected");
                            item.setAttribute("aria-pressed", "false");
                        });

                    button.classList.add("selected");
                    button.setAttribute("aria-pressed", "true");

                    // Preserve the exact datetime returned by Flask.
                    startTimeInput.value = slot;

                    showMessage(
                        `Selected appointment time: ${formatTime(slot)}`,
                        "success"
                    );
                });

                slotsContainer.appendChild(button);
            });

        } catch (error) {
            if (currentRequest !== requestNumber) return;

            console.error("Available slots error:", error);

            showSlotMessage(
                "Unable to load slots. Please refresh or choose another date."
            );

            showMessage(error.message, "error");
        }
    }

    // Refresh slots whenever the patient changes the date.
    dateInput.addEventListener("change", loadAvailableSlots);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearMessage();

        if (!doctorId) {
            showMessage("Doctor information is missing.", "error");
            return;
        }

        if (!dateInput.value) {
            showMessage("Please select an appointment date.", "error");
            dateInput.focus();
            return;
        }

        if (dateInput.value < getToday()) {
            showMessage("Please choose a future date.", "error");
            return;
        }

        if (!startTimeInput.value) {
            showMessage("Please select an available time slot.", "error");
            slotsContainer.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
            return;
        }

        const submitButton = form.querySelector('[type="submit"]');
        const originalButtonText = submitButton?.textContent || "Book Appointment";

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Booking...";
        }

        try {
            const formData = new URLSearchParams();

            // Send only the fields expected by the booking route.
            formData.set("doctor_id", doctorId);
            formData.set("start_time", startTimeInput.value);
            formData.set(
                "reason",
                form.querySelector('[name="reason"]')?.value?.trim() || ""
            );

            if (csrfInput?.value) {
                formData.set("csrf_token", csrfInput.value);
            }

            const headers = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded"
            };

            if (csrfInput?.value) {
                headers["X-CSRFToken"] = csrfInput.value;
            }

            const response = await fetch(form.action, {
                method: "POST",
                headers,
                body: formData.toString(),
                credentials: "same-origin"
            });

            const contentType = response.headers.get("content-type") || "";

            if (!contentType.includes("application/json")) {
                throw new Error(
                    "The server returned an unexpected response. Check the Flask terminal for errors."
                );
            }

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.message || "Appointment booking failed."
                );
            }

            showMessage(
                data.message || "Appointment booked successfully!",
                "success"
            );

            if (data.redirect_url) {
                window.location.assign(data.redirect_url);
            }

        } catch (error) {
            console.error("Booking error:", error);
            showMessage(error.message, "error");
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
            }
        }
    });

    // Load slots automatically if the date field already has a value.
    if (dateInput.value) {
        loadAvailableSlots();
    } else {
        showSlotMessage("Please select a date to view available slots.");
    }
});
