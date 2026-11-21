import Link from "next/link";

/** The navy bar at the top of every public page. */
export function PublicHeader() {
  return (
    <header className="bg-portal-navy px-5 py-3.5">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-0.5">
        <Link href="/" className="text-lg font-bold text-white">
          Picnic Portal
        </Link>
        <div className="text-[13px] text-[#C9D6E0]">Transport Department, Government of Assam</div>
      </div>
    </header>
  );
}

/** The emergency numbers and the small print at the foot of the public pages. */
export function PublicFooter() {
  return (
    <footer className="bg-portal-navy mt-auto px-5 py-5 text-white">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-3">
        <div>
          <div className="text-[13px] text-[#C9D6E0]">In an emergency</div>
          <div className="text-lg font-bold">
            Call <a href="tel:112">112</a> · Ambulance <a href="tel:108">108</a>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-[13px] text-[#C9D6E0]">
          <span>Transport Department, Government of Assam</span>
          <Link href="/login" className="underline">
            Officer login
          </Link>
        </div>
      </div>
    </footer>
  );
}

/** Frame of a public page: header, light background, phone-width column on large screens. */
export function PublicPage({
  children,
  footer = false,
}: {
  children: React.ReactNode;
  footer?: boolean;
}) {
  return (
    <div className="bg-portal-bg text-portal-navy flex min-h-dvh flex-1 flex-col">
      <PublicHeader />
      {children}
      {footer && <PublicFooter />}
    </div>
  );
}

/** The centred column that holds a public page's content. */
export function Column({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <main className={`mx-auto flex w-full max-w-xl flex-col gap-4 px-5 py-5 ${className}`}>
      {children}
    </main>
  );
}
