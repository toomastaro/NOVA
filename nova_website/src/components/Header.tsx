import { Button } from "@/components/ui/button";

const Header = () => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <a href="#" className="flex items-center gap-1 text-2xl font-bold">
          <span className="text-foreground">N</span>
          <span className="text-primary">☐</span>
          <span className="text-foreground">VA</span>
        </a>

        <nav className="hidden md:flex items-center gap-6">
          <a href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Функции
          </a>
          <a href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Цены
          </a>
          <Button variant="outline" size="sm" asChild>
            <a href="https://t.me/mousesquad" target="_blank" rel="noopener noreferrer">
              Поддержка
            </a>
          </Button>
        </nav>
      </div>
    </header>
  );
};

export default Header;
