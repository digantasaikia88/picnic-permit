import { ChevronRightIcon } from "lucide-react";
import Link from "next/link";

import { Notice, Section } from "@/components/apply/fields";
import { PublicPage } from "@/components/public/shell";
import { StatusSearchBox } from "@/components/public/status-parts";

const RULES = [
  {
    photo: "/photos/vehicles.webp",
    alt: "Buses, travellers and cars parked at a riverside picnic spot",
    title: "A seat for everyone",
    text: "Take only as many people as the vehicle has seats. Nobody on the roof, the footboard or in the boot.",
  },
  {
    photo: "/photos/driver.webp",
    alt: "A bus driver in uniform, seat belt on, calm at the wheel on a hill road. Signs read: Drive sober, arrive safe. A drunk driver is a danger to everyone.",
    title: "A sober, rested driver",
    text: "No alcohol before or during the journey. The driver follows speed limits and slows down on hills and bends.",
  },
  {
    photo: "/photos/evening.webp",
    alt: "Boats on a calm river in soft evening light",
    title: "Home before dark",
    text: "Leave after 7:00 AM and be back by 6:00 PM. Choose one picnic spot within 60 minutes’ drive.",
  },
];

const STEPS = [
  "You apply with your group, vehicle and driver details.",
  "The DTO, the police and the DC office check your application. You get an SMS at each stage.",
  "After final approval you get an SMS. Download the permit from this portal: it carries a large QR code. Print it and paste the QR code inside the windscreen.",
];

export default function LandingPage() {
  return (
    <PublicPage footer>
      {/* Hero */}
      <div className="relative">
        {/* eslint-disable-next-line @next/next/no-img-element -- a small local file, already compressed */}
        <img
          src="/photos/hero.webp"
          alt="Families at a riverside picnic below green hills in Assam"
          width={1280}
          height={721}
          fetchPriority="high"
          className="h-72 w-full object-cover sm:h-96"
        />
        <div className="from-portal-navy/90 via-portal-navy/45 absolute inset-0 bg-linear-to-t to-transparent" />
        <div className="absolute inset-x-0 bottom-0 px-5 pb-5">
          <div className="mx-auto flex w-full max-w-xl flex-col gap-1.5 text-white">
            <h1 className="text-[26px] leading-tight font-bold sm:text-3xl">
              Bring everyone home with good memories.
            </h1>
            <p className="text-[15px] leading-snug text-[#E6EDF2]">
              Get your Picnic/Recreational Journey Permit before you set out. No login needed.
            </p>
          </div>
        </div>
      </div>

      <main className="mx-auto flex w-full max-w-xl flex-col gap-5 px-5 py-5">
        <div className="flex flex-col gap-2">
          <Link
            href="/apply"
            className="bg-portal-blue hover:bg-portal-navy flex h-14 items-center justify-center rounded-md px-4 text-lg font-semibold text-white"
          >
            Apply for a permit
          </Link>
          <p className="text-portal-muted text-center text-[13px]">
            Apply at least 7 days before your date of travel.
          </p>
        </div>

        <Section title="Already applied?">
          <StatusSearchBox />
        </Section>

        <section className="flex flex-col gap-3">
          <h2 className="text-xl font-bold">A few simple rules keep the day happy.</h2>
          {RULES.map((rule) => (
            <article
              key={rule.title}
              className="border-portal-line overflow-hidden rounded-lg border bg-white"
            >
              {/* All three pictures take the same 16:9 frame, so the cards line up. */}
              {/* eslint-disable-next-line @next/next/no-img-element -- a small local file, already compressed */}
              <img
                src={rule.photo}
                alt={rule.alt}
                width={800}
                height={450}
                loading="lazy"
                className="aspect-video w-full object-cover"
              />
              <div className="flex flex-col gap-1 p-4">
                <h3 className="text-[17px] font-bold">{rule.title}</h3>
                <p className="text-[15px] leading-snug">{rule.text}</p>
              </div>
            </article>
          ))}
          <a
            href="/sop.pdf"
            target="_blank"
            rel="noopener"
            className="text-portal-blue text-[15px] font-semibold underline"
          >
            Read all the rules in the SOP (PDF)
          </a>
        </section>

        <Section title="How the permit works">
          <ol className="flex flex-col gap-3">
            {STEPS.map((text, index) => (
              <li key={text} className="flex items-start gap-3">
                <span className="bg-portal-navy flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white">
                  {index + 1}
                </span>
                <span className="pt-1 text-[15px] leading-snug">{text}</span>
              </li>
            ))}
          </ol>
        </Section>

        <nav aria-label="More" className="border-portal-line rounded-lg border bg-white">
          <Link
            href="/emergency-contacts"
            className="text-portal-blue flex min-h-12 items-center justify-between gap-3 px-4 text-[15px] font-semibold"
          >
            District emergency contacts
            <ChevronRightIcon aria-hidden="true" className="size-5" />
          </Link>
        </nav>

        <Notice tone="info" title="Need help with the form?">
          Apply through your nearest Public Facilitation Centre or Common Service Centre. Carry the
          group leader&rsquo;s mobile phone for the OTP.
        </Notice>
      </main>
    </PublicPage>
  );
}
