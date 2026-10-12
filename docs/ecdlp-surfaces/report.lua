-- Document rendering only: embed vector figures with pdflatex.
function Image(element)
  element.src = element.src:gsub("%.svg$", ".pdf")
  return element
end

function Code(element)
  if FORMAT:match("latex") then
    -- xurl permits line breaks in long repository paths and identifiers.
    return pandoc.RawInline("latex", "\\path|" .. element.text .. "|")
  end
end
