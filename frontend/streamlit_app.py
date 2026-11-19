import os
from datetime import date, datetime
from typing import Any, Optional

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Diagnosio | Diagnostic Booking Portal",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Session State & REST API Helpers
# ---------------------------------------------------------------------------


def init_session_state() -> None:
    defaults = {
        "access_token": None,
        "user_role": None,
        "user_email": None,
        "user_full_name": None,
        "user_id": None,
        "api_base_url": API_BASE_URL,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def logout_user() -> None:
    st.session_state["access_token"] = None
    st.session_state["user_role"] = None
    st.session_state["user_email"] = None
    st.session_state["user_full_name"] = None
    st.session_state["user_id"] = None


def get_auth_headers() -> dict[str, str]:
    token = st.session_state.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def extract_error_detail(response: requests.Response) -> str:
    try:
        data = response.json()
        detail = data.get("detail")
        if isinstance(detail, list):
            return "; ".join(str(item.get("msg", item)) for item in detail)
        if detail:
            return str(detail)
    except ValueError:
        pass
    return f"Request failed with status {response.status_code}."


def api_request(
    method: str,
    path: str,
    json_body: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    authenticated: bool = False,
) -> tuple[Optional[requests.Response], Optional[str]]:
    url = f"{st.session_state['api_base_url'].rstrip('/')}{path}"
    headers = get_auth_headers() if authenticated else {}
    try:
        response = requests.request(
            method=method,
            url=url,
            json=json_body,
            params=params,
            headers=headers,
            timeout=10,
        )
        return response, None
    except requests.RequestException as exc:
        return None, f"Could not reach FastAPI server at {url}: {exc}"


# ---------------------------------------------------------------------------
# Authentication View (Login / Register)
# ---------------------------------------------------------------------------


def render_auth_view() -> None:
    st.title("Diagnosio")
    st.caption("Multi-role diagnostic test booking and centre management portal")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary")

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                response, err = api_request(
                    "POST",
                    "/auth/login",
                    json_body={"email": email.strip(), "password": password},
                )
                if err:
                    st.error(err)
                elif response is not None and response.status_code == 200:
                    data = response.json()
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["user_role"] = data["role"]
                    st.session_state["user_email"] = data["email"]
                    st.session_state["user_full_name"] = data["full_name"]
                    st.session_state["user_id"] = data["user_id"]
                    st.success("Logged in successfully.")
                    st.rerun()
                elif response is not None:
                    st.error(extract_error_detail(response))

    with register_tab:
        with st.form("register_form"):
            full_name = st.text_input("Full Name")
            email = st.text_input("Email Address")
            password = st.text_input("Password (minimum 6 characters)", type="password")
            role_label = st.selectbox(
                "Account Role",
                options=["Patient", "Diagnostic Centre Admin"],
            )
            submitted = st.form_submit_button("Create Account", type="primary")

        if submitted:
            role_value = "PATIENT" if role_label == "Patient" else "CENTRE_ADMIN"
            if not full_name or not email or len(password) < 6:
                st.error("Please fill all fields and use a password with at least 6 characters.")
            else:
                response, err = api_request(
                    "POST",
                    "/auth/register",
                    json_body={
                        "full_name": full_name.strip(),
                        "email": email.strip(),
                        "password": password,
                        "role": role_value,
                    },
                )
                if err:
                    st.error(err)
                elif response is not None and response.status_code == 201:
                    data = response.json()
                    st.session_state["access_token"] = data["access_token"]
                    st.session_state["user_role"] = data["role"]
                    st.session_state["user_email"] = data["email"]
                    st.session_state["user_full_name"] = data["full_name"]
                    st.session_state["user_id"] = data["user_id"]
                    st.success("Account registered and logged in.")
                    st.rerun()
                elif response is not None:
                    st.error(extract_error_detail(response))


# ---------------------------------------------------------------------------
# Patient Workspace (PATIENT)
# ---------------------------------------------------------------------------


def render_patient_browse_tab() -> None:
    st.subheader("Browse Diagnostic Centres & Book Tests")

    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("Search by centre name or address", key="patient_search")
    with col2:
        city_filter = st.text_input("Filter by city", key="patient_city")

    params: dict[str, Any] = {}
    if search_query.strip():
        params["search"] = search_query.strip()
    if city_filter.strip():
        params["city"] = city_filter.strip()

    response, err = api_request("GET", "/centres/", params=params)
    if err:
        st.error(err)
        return
    if response is None or response.status_code != 200:
        st.error(extract_error_detail(response) if response else "Failed to load centres.")
        return

    centres = response.json()
    if not centres:
        st.info("No diagnostic centres found matching your filter criteria.")
        return

    centre_map = {
        f"{c['name']} ({c['city']}) - {c['opening_hour']:02d}:00 to {c['closing_hour']:02d}:00": c
        for c in centres
    }
    selected_centre_label = st.selectbox(
        "Select Diagnostic Centre",
        options=list(centre_map.keys()),
    )
    selected_centre = centre_map[selected_centre_label]

    m1, m2, m3 = st.columns(3)
    m1.metric("City", selected_centre["city"])
    m2.metric(
        "Operating Hours",
        f"{selected_centre['opening_hour']:02d}:00 - {selected_centre['closing_hour']:02d}:00",
    )
    m3.metric("Max Capacity / Slot", selected_centre["max_capacity_per_slot"])
    st.write(f"Address: {selected_centre['address']}")

    tests = selected_centre.get("tests", [])
    if not tests:
        st.warning("This diagnostic centre has not published any available tests yet.")
        return

    st.write("Available Diagnostic Tests")
    st.dataframe(
        [
            {
                "Test Name": t["test_name"],
                "Description": t["description"] or "-",
                "Price": float(t["price"]),
            }
            for t in tests
        ],
        use_container_width=True,
        hide_index=True,
    )

    test_options = {
        f"{t['test_name']} (Rs. {float(t['price']):.2f})": t for t in tests
    }
    selected_test_labels = st.multiselect(
        "Select One or More Diagnostic Tests",
        options=list(test_options.keys()),
    )

    selected_date = st.date_input(
        "Select Appointment Date",
        value=date.today(),
        min_value=date.today(),
    )

    slots_resp, slots_err = api_request(
        "GET",
        f"/centres/{selected_centre['id']}/slots",
        params={"booking_date": selected_date.isoformat()},
    )
    if slots_err:
        st.error(slots_err)
        return
    if slots_resp is None or slots_resp.status_code != 200:
        st.error(extract_error_detail(slots_resp) if slots_resp else "Failed to load time slots.")
        return

    slots = slots_resp.json()
    slot_options = {}
    for slot in slots:
        status_note = (
            f"{slot['available_spots']}/{slot['max_capacity']} spots left"
            if slot["is_available"]
            else "FULL"
        )
        slot_options[f"{slot['label']} ({status_note})"] = slot

    selected_slot_label = st.selectbox(
        "Select Fixed 1-Hour Time Slot",
        options=list(slot_options.keys()),
    )
    selected_slot = slot_options[selected_slot_label]

    total_price = sum(float(test_options[lbl]["price"]) for lbl in selected_test_labels)
    st.write(f"Selected Tests Total: Rs. {total_price:.2f}")

    if st.button("Confirm Slot Booking", type="primary"):
        if not selected_test_labels:
            st.error("Please select at least one diagnostic test.")
        else:
            centre_test_ids = [
                test_options[lbl]["centre_test_id"] for lbl in selected_test_labels
            ]
            book_resp, book_err = api_request(
                "POST",
                "/bookings/",
                json_body={
                    "centre_id": selected_centre["id"],
                    "centre_test_ids": centre_test_ids,
                    "appointment_time": selected_slot["slot_time"],
                },
                authenticated=True,
            )
            if book_err:
                st.error(book_err)
            elif book_resp is not None and book_resp.status_code == 201:
                created = book_resp.json()
                st.success(
                    f"Booking #{created['id']} created for {selected_slot['label']} "
                    f"on {selected_date.isoformat()} (Total: Rs. {float(created['total_amount']):.2f}). "
                    "Status is PENDING until payment is confirmed at the diagnostic centre."
                )
            elif book_resp is not None and book_resp.status_code == 409:
                st.warning(f"Slot Conflict (409): {extract_error_detail(book_resp)}")
            elif book_resp is not None:
                st.error(extract_error_detail(book_resp))


def render_patient_bookings_tab() -> None:
    st.subheader("My Bookings")

    response, err = api_request("GET", "/bookings/my", authenticated=True)
    if err:
        st.error(err)
        return
    if response is None or response.status_code != 200:
        st.error(extract_error_detail(response) if response else "Failed to load bookings.")
        return

    bookings = response.json()
    if not bookings:
        st.info("You have not made any diagnostic bookings yet.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bookings", len(bookings))
    c2.metric("Pending", sum(1 for b in bookings if b["status"] == "PENDING"))
    c3.metric("Confirmed", sum(1 for b in bookings if b["status"] == "CONFIRMED"))
    c4.metric("Cancelled", sum(1 for b in bookings if b["status"] == "CANCELLED"))

    for booking in bookings:
        appt_display = datetime.fromisoformat(booking["appointment_time"]).strftime(
            "%Y-%m-%d %H:%M"
        )
        with st.container(border=True):
            header_col, action_col = st.columns([3, 1])
            with header_col:
                st.markdown(
                    f"**Booking #{booking['id']} — {booking['centre_name']} ({booking['centre_city']})**"
                )
                st.write(
                    f"Slot: {appt_display} | Status: {booking['status']} | "
                    f"Payment: {booking['payment_status']} | "
                    f"Total Snapshot: Rs. {float(booking['total_amount']):.2f}"
                )
                items_rows = [
                    {
                        "Diagnostic Test": item["test_name_snapshot"],
                        "Price Snapshot (Rs.)": float(item["price_snapshot"]),
                    }
                    for item in booking.get("items", [])
                ]
                if items_rows:
                    st.dataframe(items_rows, use_container_width=True, hide_index=True)

            with action_col:
                if booking["status"] == "PENDING":
                    st.info("Awaiting payment confirmation at diagnostic centre")
                    if st.button(
                        "Cancel Booking",
                        key=f"cancel_{booking['id']}",
                        use_container_width=True,
                    ):
                        cancel_resp, cancel_err = api_request(
                            "POST",
                            f"/bookings/{booking['id']}/cancel",
                            authenticated=True,
                        )
                        if cancel_err:
                            st.error(cancel_err)
                        elif cancel_resp is not None and cancel_resp.status_code == 200:
                            st.success(
                                f"Booking #{booking['id']} cancelled and time slot released."
                            )
                            st.rerun()
                        elif cancel_resp is not None:
                            st.error(extract_error_detail(cancel_resp))
                elif booking["status"] == "CONFIRMED":
                    st.success("Confirmed & Paid (Locked)")
                else:
                    st.caption("Cancelled")


def render_patient_workspace() -> None:
    st.title("Patient Portal")
    tab1, tab2 = st.tabs(["Browse & Book Tests", "My Bookings"])
    with tab1:
        render_patient_browse_tab()
    with tab2:
        render_patient_bookings_tab()


# ---------------------------------------------------------------------------
# Diagnostic Centre Admin Workspace (CENTRE_ADMIN)
# ---------------------------------------------------------------------------


def fetch_admin_centre_dashboard(
    booking_date: Optional[date] = None,
    booking_status: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], Optional[int], Optional[str]]:
    params: dict[str, Any] = {}
    if booking_date is not None:
        params["booking_date"] = booking_date.isoformat()
    if booking_status and booking_status != "ALL":
        params["status"] = booking_status

    response, err = api_request(
        "GET",
        "/centres/my-centre",
        params=params,
        authenticated=True,
    )
    if err:
        return None, None, err
    if response is None:
        return None, None, "Empty response from backend."
    if response.status_code == 200:
        return response.json(), 200, None
    return None, response.status_code, extract_error_detail(response)


def render_admin_onboarding_tab(
    dashboard: Optional[dict[str, Any]],
    status_code: Optional[int],
    err: Optional[str],
) -> None:
    st.subheader("Centre Onboarding & Profile")

    if status_code == 404:
        st.info("You have not registered your diagnostic centre yet. Complete onboarding below.")
        with st.form("onboard_centre_form"):
            name = st.text_input("Diagnostic Centre Name")
            city = st.text_input("City")
            address = st.text_area("Full Street Address")
            c1, c2, c3 = st.columns(3)
            with c1:
                opening_hour = st.number_input(
                    "Opening Hour (0-23)",
                    min_value=0,
                    max_value=23,
                    value=9,
                    step=1,
                )
            with c2:
                closing_hour = st.number_input(
                    "Closing Hour (1-24)",
                    min_value=1,
                    max_value=24,
                    value=17,
                    step=1,
                )
            with c3:
                max_capacity = st.number_input(
                    "Max Capacity per 1-Hour Slot",
                    min_value=1,
                    max_value=500,
                    value=3,
                    step=1,
                )
            submitted = st.form_submit_button("Register Diagnostic Centre", type="primary")

        if submitted:
            if not name.strip() or not city.strip() or not address.strip():
                st.error("Please fill in centre name, city, and address.")
            elif int(closing_hour) <= int(opening_hour):
                st.error("Closing hour must be greater than opening hour.")
            else:
                resp, req_err = api_request(
                    "POST",
                    "/centres/",
                    json_body={
                        "name": name.strip(),
                        "city": city.strip(),
                        "address": address.strip(),
                        "opening_hour": int(opening_hour),
                        "closing_hour": int(closing_hour),
                        "max_capacity_per_slot": int(max_capacity),
                    },
                    authenticated=True,
                )
                if req_err:
                    st.error(req_err)
                elif resp is not None and resp.status_code == 201:
                    st.success("Diagnostic centre onboarded successfully.")
                    st.rerun()
                elif resp is not None:
                    st.error(extract_error_detail(resp))
        return

    if err or dashboard is None:
        st.error(err or "Unable to load centre profile.")
        return

    centre = dashboard["centre"]
    stats = dashboard["stats"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Max Capacity / Slot", centre["max_capacity_per_slot"])
    m2.metric("Offered Tests", stats["offered_tests_count"])
    m3.metric("Pending Bookings", stats["pending_bookings"])
    m4.metric("Confirmed Bookings", stats["confirmed_bookings"])

    st.write(f"**Centre Name:** {centre['name']}")
    st.write(f"**City:** {centre['city']}")
    st.write(f"**Address:** {centre['address']}")
    st.write(
        f"**Operating Hours:** {centre['opening_hour']:02d}:00 - {centre['closing_hour']:02d}:00 "
        "(fixed 1-hour slots)"
    )


def render_admin_tests_tab(dashboard: Optional[dict[str, Any]]) -> None:
    st.subheader("Manage Diagnostic Tests")

    if dashboard is None:
        st.info("Please onboard your diagnostic centre in Tab 1 first.")
        return

    centre = dashboard["centre"]

    with st.form("add_test_form"):
        test_name = st.text_input("Test Name (e.g., Complete Blood Count, Lipid Profile)")
        description = st.text_area("Test Description")
        c1, c2 = st.columns(2)
        with c1:
            price = st.number_input("Price (Rs.)", min_value=1.0, value=500.0, step=50.0)
        with c2:
            is_available = st.checkbox("Available for patient booking", value=True)
        submitted = st.form_submit_button("Add or Update Test", type="primary")

    if submitted:
        if not test_name.strip():
            st.error("Please enter a diagnostic test name.")
        else:
            resp, req_err = api_request(
                "POST",
                f"/centres/{centre['id']}/tests",
                json_body={
                    "test_name": test_name.strip(),
                    "description": description.strip(),
                    "price": float(price),
                    "is_available": is_available,
                },
                authenticated=True,
            )
            if req_err:
                st.error(req_err)
            elif resp is not None and resp.status_code == 201:
                st.success(f"Saved diagnostic test '{test_name.strip()}' and refreshed catalogue.")
                st.rerun()
            elif resp is not None:
                st.error(extract_error_detail(resp))

    st.write("Currently Offered Tests")
    tests = centre.get("tests", [])
    if not tests:
        st.info("No diagnostic tests added yet.")
    else:
        st.dataframe(
            [
                {
                    "Centre Test ID": t["centre_test_id"],
                    "Test Name": t["test_name"],
                    "Description": t["description"] or "-",
                    "Price (Rs.)": float(t["price"]),
                    "Available": "Yes" if t["is_available"] else "No",
                }
                for t in tests
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_admin_appointments_tab(dashboard: Optional[dict[str, Any]]) -> None:
    st.subheader("Centre Appointments Dashboard")

    if dashboard is None:
        st.info("Please onboard your diagnostic centre in Tab 1 first.")
        return

    f1, f2, f3 = st.columns([1, 1, 1])
    with f1:
        use_date_filter = st.checkbox("Filter by appointment date", value=False)
    with f2:
        selected_date = st.date_input(
            "Appointment Date",
            value=date.today(),
            disabled=not use_date_filter,
        )
    with f3:
        status_filter = st.selectbox(
            "Booking Status",
            options=["ALL", "PENDING", "CONFIRMED", "CANCELLED"],
        )

    filtered_dashboard, _, err = fetch_admin_centre_dashboard(
        booking_date=selected_date if use_date_filter else None,
        booking_status=status_filter,
    )
    if err or filtered_dashboard is None:
        st.error(err or "Unable to fetch appointments.")
        return

    bookings = filtered_dashboard.get("bookings", [])
    if not bookings:
        st.info("No patient bookings match the current filters.")
        return

    rows = []
    for b in bookings:
        test_names = ", ".join(item["test_name_snapshot"] for item in b.get("items", []))
        appt_display = datetime.fromisoformat(b["appointment_time"]).strftime("%Y-%m-%d %H:%M")
        rows.append(
            {
                "Booking ID": b["id"],
                "Patient Name": b["patient_name"],
                "Patient Email": b["patient_email"],
                "Booked Tests": test_names,
                "Slot Time": appt_display,
                "Total (Rs.)": float(b["total_amount"]),
                "Booking Status": b["status"],
                "Payment Status": b["payment_status"],
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    pending_bookings = [b for b in bookings if b["status"] == "PENDING"]
    if pending_bookings:
        st.subheader("Pending Payment Confirmations")
        for b in pending_bookings:
            appt_display = datetime.fromisoformat(b["appointment_time"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            test_names = ", ".join(item["test_name_snapshot"] for item in b.get("items", []))
            with st.container(border=True):
                info_col, btn_col = st.columns([3, 1])
                with info_col:
                    st.markdown(
                        f"**Booking #{b['id']} — {b['patient_name']} ({b['patient_email']})**"
                    )
                    st.write(
                        f"Slot: {appt_display} | Tests: {test_names} | "
                        f"Amount Due: Rs. {float(b['total_amount']):.2f}"
                    )
                with btn_col:
                    if st.button(
                        "Confirm Payment (Paid at Centre)",
                        key=f"admin_confirm_pay_{b['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        confirm_resp, confirm_err = api_request(
                            "POST",
                            f"/payments/bookings/{b['id']}/confirm",
                            authenticated=True,
                        )
                        if confirm_err:
                            st.error(confirm_err)
                        elif confirm_resp is not None and confirm_resp.status_code == 200:
                            st.success(
                                f"Booking #{b['id']} payment confirmed and booking locked."
                            )
                            st.rerun()
                        elif confirm_resp is not None:
                            st.error(extract_error_detail(confirm_resp))


def render_centre_admin_workspace() -> None:
    st.title("Diagnostic Centre Admin Portal")
    dashboard, status_code, err = fetch_admin_centre_dashboard()

    tab1, tab2, tab3 = st.tabs(
        [
            "Centre Onboarding & Profile",
            "Manage Diagnostic Tests",
            "Centre Appointments Dashboard",
        ]
    )
    with tab1:
        render_admin_onboarding_tab(dashboard, status_code, err)
    with tab2:
        render_admin_tests_tab(dashboard)
    with tab3:
        render_admin_appointments_tab(dashboard)


# ---------------------------------------------------------------------------
# Main App Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    init_session_state()

    with st.sidebar:
        st.header("Diagnosio")
        st.session_state["api_base_url"] = st.text_input(
            "FastAPI Base URL",
            value=st.session_state["api_base_url"],
        )

        if st.session_state.get("access_token"):
            st.divider()
            st.write(f"**User:** {st.session_state['user_full_name']}")
            st.write(f"**Email:** {st.session_state['user_email']}")
            st.write(f"**Role:** {st.session_state['user_role']}")
            st.write(f"**User ID:** {st.session_state['user_id']}")
            if st.button("Logout", use_container_width=True):
                logout_user()
                st.rerun()

    if not st.session_state.get("access_token"):
        render_auth_view()
    elif st.session_state.get("user_role") == "CENTRE_ADMIN":
        render_centre_admin_workspace()
    else:
        render_patient_workspace()


if __name__ == "__main__":
    main()
