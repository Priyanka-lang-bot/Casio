import { redirect } from "next/navigation";

// No marketing homepage: "/" goes straight into the app.
// Signed-out visitors are sent on to /login by the protected app layout.
export default function Home() {
  redirect("/overview");
}
