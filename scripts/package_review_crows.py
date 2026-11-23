"""Package current encoded review frames with the additive crow selector."""
import package_review as package
import build_crows as current
package.current = current
if __name__ == '__main__':
    package.main()
