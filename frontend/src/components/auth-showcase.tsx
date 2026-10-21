import {
  ChartColumn,
  Database,
  DatabaseZap,
  FileCode2,
  FileSpreadsheet,
  FolderOpen,
  MessageSquareText,
  Server,
  ShieldCheck,
  Table2,
} from "lucide-react";

import { AnimatedLogo } from "@/components/layout/animated-logo";
import { OrbitingCircles } from "@/components/ui/orbiting-circles";
import { Ripple } from "@/components/ui/ripple";
import { ToneIcon, type Tone } from "@/components/ui/tone-icon";

function OrbitIcon(props: { icon: typeof Database; tone: Tone }) {
  return (
    <ToneIcon
      {...props}
      className="size-full rounded-2xl shadow-lg backdrop-blur-sm"
    />
  );
}

/**
 * Левая панель страниц входа: логотип и название в центре, вокруг на орбитах
 * вращаются базы данных, таблицы и этапы обработки вопроса.
 */
export function AuthShowcase() {
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      <Ripple mainCircleSize={160} numCircles={9} mainCircleOpacity={0.18} />

      <div className="absolute inset-0 flex items-center justify-center">
        <OrbitingCircles radius={140} duration={24} iconSize={44} path={false}>
          <OrbitIcon icon={Database} tone={1} />
          <OrbitIcon icon={Table2} tone={2} />
        </OrbitingCircles>
        <OrbitingCircles
          radius={210}
          duration={32}
          iconSize={50}
          path={false}
          reverse
        >
          <OrbitIcon icon={MessageSquareText} tone={3} />
          <OrbitIcon icon={FileCode2} tone={4} />
          <OrbitIcon icon={ShieldCheck} tone={5} />
        </OrbitingCircles>
        <OrbitingCircles radius={285} duration={44} iconSize={58} path={false}>
          <OrbitIcon icon={Server} tone={6} />
          <OrbitIcon icon={FolderOpen} tone={7} />
          <OrbitIcon icon={ChartColumn} tone={1} />
          <OrbitIcon icon={DatabaseZap} tone={8} />
          <OrbitIcon icon={FileSpreadsheet} tone={2} />
        </OrbitingCircles>
      </div>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-4">
        <AnimatedLogo />
        <span className="bg-gradient-to-b from-foreground to-foreground/30 bg-clip-text text-6xl leading-none font-semibold tracking-tight text-transparent xl:text-7xl">
          Suhbat2DB
        </span>
      </div>
    </div>
  );
}
