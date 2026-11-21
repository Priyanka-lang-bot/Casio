import { Landing } from "@/components/landing/landing";
import { getCurrentUser } from "@/lib/session";

// The public landing page. Signed-in visitors see "Open your wallet" instead
// of the demo and log-in buttons.
export default async function Home() {
  let signedIn = false;
  try {
    signedIn = !!(await getCurrentUser());
  } catch {
    signedIn = false; // backend unreachable: still show the page
  }
  return <Landing signedIn={signedIn} />;
}
