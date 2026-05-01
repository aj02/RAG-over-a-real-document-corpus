/**
 * Example questions surfaced on the /ask landing.
 *
 * Picked to span:
 *   - SEBI vs RBI
 *   - quick lookup vs synthesis
 *   - questions where the system *should* have an answer in the indexed corpus
 */

export interface ExampleQuestion {
  id: string;
  question: string;
  category: "SEBI" | "RBI" | "Both";
  hint: string;
}

export const EXAMPLE_QUESTIONS: ExampleQuestion[] = [
  {
    id: "ex1",
    question:
      "What is the minimum corpus size required for a Category I AIF?",
    category: "SEBI",
    hint: "Lookup, single doc",
  },
  {
    id: "ex2",
    question:
      "What KYC documentation must banks collect from low-risk customers?",
    category: "RBI",
    hint: "Lookup, KYC Master Direction",
  },
  {
    id: "ex3",
    question:
      "How does an FPI register with SEBI and what role does the DDP play?",
    category: "SEBI",
    hint: "Process question",
  },
  {
    id: "ex4",
    question:
      "What are the loading limits for full-KYC Prepaid Payment Instruments?",
    category: "RBI",
    hint: "Specific limit lookup",
  },
  {
    id: "ex5",
    question:
      "How do KYC requirements compare for opening a bank account vs issuing a full-KYC PPI?",
    category: "RBI",
    hint: "Multi-doc synthesis",
  },
  {
    id: "ex6",
    question:
      "What disclosure obligations apply to a listed entity for price-sensitive information under LODR?",
    category: "SEBI",
    hint: "Timelines + categories",
  },
  {
    id: "ex7",
    question:
      "What is the per-financial-year limit under the Liberalised Remittance Scheme?",
    category: "RBI",
    hint: "Quick lookup",
  },
  {
    id: "ex8",
    question:
      "How do the obligations of an Investment Adviser differ from those of a Research Analyst?",
    category: "SEBI",
    hint: "Multi-doc synthesis",
  },
];
