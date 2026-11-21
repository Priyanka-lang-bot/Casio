import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "AI Finance Coach · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="AI Finance Coach"
      description="Ask questions about your money in everyday language."
      phase="Phase 5"
      bullets={[
        "Ask “Where did most of my money go?” or “Can I afford a laptop?”",
        "Answers use your real CASIO data, looked up and calculated by CASIO itself",
        "Explains finance in simple terms. It won't recommend specific stocks or act as a licensed adviser",
      ]}
    />
  );
}
