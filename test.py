import asyncio

from services.search.search_manager import search_web


async def main():

    query = "latest AI developments"

    result = await search_web(query)

    print("\n" + "=" * 60)
    print("SEARCH TEST")
    print("=" * 60)

    print(f"Success  : {result['success']}")
    print(f"Query    : {result['query']}")
    print(f"Provider : {result['provider']}")

    print("=" * 60)

    if result["success"]:

        for index, item in enumerate(
            result["results"],
            start=1,
        ):
            print(f"\n{index}. {item['title']}")
            print(f"URL      : {item['url']}")
            print(f"Provider : {item['provider']}")
            print(f"Content  : {item['description']}")

    else:

        print("\nERROR:")
        print(result["error"])

        print("\nProvider Errors:")

        for error in result.get("provider_errors", []):
            print(
                f"- {error['provider']}: "
                f"{error['error']}"
            )


if __name__ == "__main__":
    asyncio.run(main())