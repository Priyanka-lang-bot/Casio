import { redirect } from "next/navigation";

// No marketing homepage: "/" goes straight to the card wallet.
// Signed-out visitors are sent on to /login by the protected app layout.
export default function Home() {
  redirect("/wallet");
}
