export function WebsiteSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "خزانة Khizana",
    alternateName: "Khizana Kuwait",
    url: process.env.NEXT_PUBLIC_APP_URL || "https://khizana.kw",
    description:
      "منصة تأجير وبيع الأزياء النسائية المصممة في الكويت — Rent or buy designer women's fashion in Kuwait",
    inLanguage: ["ar", "en"],
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate:
          (process.env.NEXT_PUBLIC_APP_URL || "https://khizana.kw") +
          "/rent?search={search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function OrganizationSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "خزانة Khizana",
    url: process.env.NEXT_PUBLIC_APP_URL || "https://khizana.kw",
    logo: (process.env.NEXT_PUBLIC_APP_URL || "https://khizana.kw") + "/logo.png",
    sameAs: [],
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer service",
      availableLanguage: ["Arabic", "English"],
      areaServed: "KW",
    },
    address: {
      "@type": "PostalAddress",
      addressCountry: "KW",
      addressLocality: "Kuwait City",
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function FAQSchema({
  faqs,
}: {
  faqs: { question: string; answer: string }[];
}) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export function ProductSchema({
  name,
  description,
  brand,
  price,
  currency,
  condition,
  availability,
}: {
  name: string;
  description: string;
  brand: string;
  price: number;
  currency?: string;
  condition?: string;
  availability?: string;
}) {
  const conditionMap: Record<string, string> = {
    NEW_WITH_TAGS: "https://schema.org/NewCondition",
    EXCELLENT: "https://schema.org/UsedCondition",
    VERY_GOOD: "https://schema.org/UsedCondition",
    GOOD: "https://schema.org/UsedCondition",
  };

  const schema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name,
    description,
    brand: {
      "@type": "Brand",
      name: brand,
    },
    offers: {
      "@type": "Offer",
      price,
      priceCurrency: currency || "KWD",
      availability: availability || "https://schema.org/InStock",
      itemCondition: conditionMap[condition || "EXCELLENT"],
      areaServed: {
        "@type": "Country",
        name: "KW",
      },
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
