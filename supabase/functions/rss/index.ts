import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
    const supabase = createClient(
        Deno.env.get('SUPABASE_URL') ?? '',
        Deno.env.get('SUPABASE_ANON_KEY') ?? ''
    )

    // 1. Fetch Metadata
    const { data: meta } = await supabase.from('podcast_meta').select('*').single()

    // 2. Fetch Episodes (Oldest to Newest)
    const { data: episodes } = await supabase
        .from('episodes')
        .select('*')
        .order('pub_date', { ascending: false })

    if (!meta) return new Response("Seed metadata not found", { status: 500 })

    // 3. Generate XML
    const itemsXml = episodes?.map(ep => {
        const pubDate = new Date(ep.pub_date).toUTCString()
        const imageTag = ep.image_url ? `<itunes:image href="${ep.image_url}"/>` : ""

        return `
    <item>
      <title><![CDATA[${ep.title}]]></title>
      <description><![CDATA[${ep.description}]]></description>
      <pubDate>${pubDate}</pubDate>
      <enclosure url="${ep.audio_url}" type="audio/mpeg" length="0"/>
      <itunes:duration>${ep.duration || "00:00:00"}</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
      ${imageTag}
      <guid isPermaLink="false">${ep.audio_url}</guid>
      <dc:creator><![CDATA[${meta.author}]]></dc:creator>
    </item>`
    }).join('')

    const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title><![CDATA[${meta.title}]]></title>
    <description><![CDATA[${meta.description}]]></description>
    <link>${meta.link}</link>
    <language>pt-br</language>
    <itunes:author>${meta.author}</itunes:author>
    <itunes:type>episodic</itunes:type>
    <itunes:owner>
      <itunes:name>${meta.author}</itunes:name>
      <itunes:email>${meta.email}</itunes:email>
    </itunes:owner>
    <itunes:image href="${meta.image_url}"/>
    <itunes:category text="Religion &amp; Spirituality">
      <itunes:category text="Christianity"/>
    </itunes:category>
    <itunes:explicit>no</itunes:explicit>
    ${itemsXml}
  </channel>
</rss>`

    return new Response(rssXml, {
        headers: { ...corsHeaders, 'Content-Type': 'application/xml; charset=utf-8' },
    })
})
