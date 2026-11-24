"""Review package dispatcher for Portia and all earlier films."""
import package_review as package
import build_portia as current
package.current = current
if __name__ == "__main__":
    package.main()
